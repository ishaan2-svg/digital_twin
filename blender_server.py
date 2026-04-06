"""
BLENDER SERVER FOR DIGITAL TWIN
================================
This script runs inside Blender and:
1. Listens for commands from the Backend/UI
2. Updates Temperature, Pressure, RUL, vibration_intensity
3. Renders a frame and sends it back

Run with:
    blender "Rocket_DigitalTwin_FINAL.blend" --python blender_server.py

Or for background (no UI):
    blender --background "Rocket_DigitalTwin_FINAL.blend" --python blender_server.py
"""

import bpy
import mathutils
import socket
import json
import threading
import struct
import io
import os
import tempfile

# =============================================================================
# CONFIGURATION
# =============================================================================

HOST = 'localhost'
PORT = 5555

CONTROLLER_NAME = "DigitalTwin_Controller"
TURBOPUMP_DRIVER_NAME = "Turbopump_NoiseDriver"

# Render settings - BALANCED QUALITY + SPEED
RENDER_WIDTH = 640
RENDER_HEIGHT = 480
RENDER_SAMPLES = 16

# Vibration speed multiplier
VIBRATION_SPEED = 10

# =============================================================================
# TEMPERATURE & PRESSURE RANGES (from UI/Backend)
# =============================================================================
# These are the ACTUAL values sent from the backend that Blender receives.
# 
# TEMPERATURE (in Celsius):
#   Backend sends: thermal_ratio * chamber_temp_max
#   Actual range: ~400°C (healthy) to ~670°C (critical)
#
#   Example values:
#   - Engine 72, Cycle 50: ~500°C (slightly red)
#   - Healthy engine:      ~400-450°C (grey)
#   - Critical engine:     ~650-670°C (red)
#
# UPDATE YOUR BLENDER MATERIAL:
#   In your ColorRamp or Map Range node, change:
#   - From:  Min=0, Max=100 (or whatever you had)
#   - To:    Min=400, Max=670
#
# This way, 400°C = grey (position 0), 670°C = red (position 1)
# And 500°C will be slightly red (position ~0.37)
# =============================================================================

# =============================================================================
# CAMERA CONTROL
# =============================================================================

# Fixed camera settings - DO NOT CHANGE
CAMERA_DISTANCE = 8.0
CAMERA_TARGET = (0.0055, 2.28, 2.676)

def get_camera_target():
    """Get the target point for camera to look at."""
    return mathutils.Vector(CAMERA_TARGET)

def setup_camera():
    """Ensure camera exists."""
    camera = bpy.data.objects.get("Camera")
    
    if not camera:
        cam_data = bpy.data.cameras.new("Camera")
        camera = bpy.data.objects.new("Camera", cam_data)
        bpy.context.scene.collection.objects.link(camera)
    
    bpy.context.scene.camera = camera
    return camera

def rotate_camera(direction, angle=15):
    """Rotate camera around the model center while maintaining CURRENT distance."""
    import math
    
    camera = bpy.data.objects.get("Camera")
    if not camera:
        camera = setup_camera()
    
    target_loc = get_camera_target()
    rel_pos = camera.location - target_loc
    current_distance = rel_pos.length
    if current_distance == 0:
        current_distance = CAMERA_DISTANCE
    
    horizontal_dist = math.sqrt(rel_pos.x**2 + rel_pos.y**2)
    if horizontal_dist == 0:
        horizontal_dist = 0.001
    theta = math.atan2(rel_pos.y, rel_pos.x)
    phi = math.atan2(rel_pos.z, horizontal_dist)
    
    angle_rad = math.radians(angle)
    
    if direction == 'left':
        theta += angle_rad
    elif direction == 'right':
        theta -= angle_rad
    elif direction == 'up':
        phi = min(phi + angle_rad * 0.5, math.radians(85))
    elif direction == 'down':
        phi = max(phi - angle_rad * 0.5, math.radians(-30))
    
    new_x = current_distance * math.cos(phi) * math.cos(theta)
    new_y = current_distance * math.cos(phi) * math.sin(theta)
    new_z = current_distance * math.sin(phi)
    
    camera.location = target_loc + mathutils.Vector((new_x, new_y, new_z))
    
    direction_vec = target_loc - camera.location
    rot_quat = direction_vec.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()
    
    return {"status": "ok", "camera_location": list(camera.location)}

def set_camera_preset(preset):
    """Set camera to a preset position while maintaining CURRENT distance."""
    import math
    
    camera = bpy.data.objects.get("Camera")
    if not camera:
        camera = setup_camera()
    
    target_loc = get_camera_target()
    current_distance = (camera.location - target_loc).length
    if current_distance == 0:
        current_distance = CAMERA_DISTANCE
    
    if preset == 'front':
        camera.location = (target_loc.x, target_loc.y - current_distance, target_loc.z)
    elif preset == 'back':
        camera.location = (target_loc.x, target_loc.y + current_distance, target_loc.z)
    elif preset == 'side':
        camera.location = (target_loc.x + current_distance, target_loc.y, target_loc.z)
    elif preset == 'side_left':
        camera.location = (target_loc.x - current_distance, target_loc.y, target_loc.z)
    elif preset == 'top':
        camera.location = (target_loc.x, target_loc.y - 0.5, target_loc.z + current_distance)
    elif preset == 'isometric':
        d = current_distance / math.sqrt(3)
        camera.location = (target_loc.x + d, target_loc.y - d, target_loc.z + d)
    elif preset == 'default':
        d = current_distance / math.sqrt(3)
        camera.location = (target_loc.x + d, target_loc.y - d, target_loc.z + d)
    
    direction_vec = target_loc - camera.location
    rot_quat = direction_vec.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()
    
    return {"status": "ok", "preset": preset, "camera_location": list(camera.location)}

def zoom_camera(delta):
    """Zoom is DISABLED - camera stays at fixed distance."""
    return {"status": "ok", "message": "Zoom disabled - fixed camera distance"}

# =============================================================================
# SETUP RENDER SETTINGS
# =============================================================================

def setup_render():
    """Configure Blender for FAST EEVEE rendering."""
    scene = bpy.context.scene
    
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'EEVEE_NEXT') else 'BLENDER_EEVEE'
    
    scene.render.resolution_x = RENDER_WIDTH
    scene.render.resolution_y = RENDER_HEIGHT
    scene.render.resolution_percentage = 100
    
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 70
    
    if hasattr(scene.eevee, 'taa_render_samples'):
        scene.eevee.taa_render_samples = RENDER_SAMPLES
    if hasattr(scene.eevee, 'taa_samples'):
        scene.eevee.taa_samples = RENDER_SAMPLES
    
    scene.render.use_motion_blur = False
    
    if hasattr(scene.eevee, 'use_bloom'):
        scene.eevee.use_bloom = False
    if hasattr(scene.eevee, 'use_ssr'):
        scene.eevee.use_ssr = False
    if hasattr(scene.eevee, 'use_gtao'):
        scene.eevee.use_gtao = False
    
    scene.render.use_simplify = True
    scene.render.simplify_subdivision = 1
    
    print(f"✓ FAST Render: {RENDER_WIDTH}x{RENDER_HEIGHT}, {RENDER_SAMPLES} samples")

# =============================================================================
# UPDATE DIGITAL TWIN
# =============================================================================

def update_digital_twin(data):
    """Update Blender scene based on received data.
    
    Temperature is passed as raw value in Celsius (~400-670 range).
    Update your Blender material's Map Range/ColorRamp to use Min=400, Max=670.
    """
    import math
    
    controller = bpy.data.objects.get(CONTROLLER_NAME)
    turbopump = bpy.data.objects.get(TURBOPUMP_DRIVER_NAME)
    
    if not controller:
        print(f"ERROR: Controller '{CONTROLLER_NAME}' not found!")
        return {"error": f"Controller '{CONTROLLER_NAME}' not found"}
    
    # DEBUG: Print what we're setting
    print(f"  -> Setting values: Temp={data.get('Temperature')}, Pressure={data.get('Pressure')}, RUL={data.get('RUL')}")
    
    if "Temperature" in data:
        controller["Temperature"] = data["Temperature"]
        print(f"     Controller Temperature is now: {controller['Temperature']}")
    
    if "Pressure" in data:
        controller["Pressure"] = data["Pressure"]
    
    if "RUL" in data:
        controller["RUL"] = data["RUL"]
    
    vibration_intensity = data.get("vibration_intensity", 0)
    if turbopump:
        turbopump["vibration_intensity"] = vibration_intensity
    
    frame = data.get("frame", 0)
    
    # CRITICAL: Force driver update by changing frame
    # This is the most reliable way to trigger driver recalculation
    current_frame = bpy.context.scene.frame_current
    bpy.context.scene.frame_set(current_frame + 1)
    bpy.context.scene.frame_set(current_frame)
    
    if frame > 0:
        if turbopump and vibration_intensity > 0:
            orig_x = -0.0056
            orig_y = 2.28
            orig_z = 2.676
            
            vib_amplitude = vibration_intensity * 0.25
            freq = 15
            
            offset_x = vib_amplitude * math.sin(frame * freq * 1.0)
            offset_y = vib_amplitude * math.sin(frame * freq * 1.3)
            offset_z = vib_amplitude * math.sin(frame * freq * 0.9) * 0.5
            
            turbopump.location.x = orig_x + offset_x
            turbopump.location.y = orig_y + offset_y
            turbopump.location.z = orig_z + offset_z
        
        bpy.context.scene.frame_set(frame * VIBRATION_SPEED)
    
    # Force updates
    controller.update_tag()
    if turbopump:
        turbopump.update_tag()
    
    bpy.context.view_layer.update()
    
    # Force depsgraph update
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
    except:
        pass
    
    return {"status": "ok"}

# =============================================================================
# RENDER FRAME
# =============================================================================

render_lock = threading.Lock()

def render_frame():
    """Render current view and return as JPEG bytes."""
    global render_lock
    
    with render_lock:
        try:
            temp_path = os.path.join(tempfile.gettempdir(), "dt_render.jpg")
            
            bpy.context.scene.render.image_settings.file_format = 'JPEG'
            bpy.context.scene.render.image_settings.quality = 90
            bpy.context.scene.render.filepath = temp_path
            
            bpy.ops.render.render(write_still=True)
            
            if os.path.exists(temp_path):
                with open(temp_path, 'rb') as f:
                    image_data = f.read()
                
                try:
                    os.remove(temp_path)
                except:
                    pass
                
                return image_data
            
            return None
            
        except Exception as e:
            print(f"Render error: {e}")
            return None

# =============================================================================
# SOCKET SERVER
# =============================================================================

class BlenderServer:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.render_mode = "eevee"
    
    def start(self):
        """Start the server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(1)
        self.socket.settimeout(1.0)
        self.running = True
        
        print(f"\n{'='*50}")
        print(f"BLENDER DIGITAL TWIN SERVER")
        print(f"{'='*50}")
        print(f"Listening on {self.host}:{self.port}")
        print(f"Render mode: {self.render_mode}")
        print(f"{'='*50}")
        print("Waiting for connection...")
        print("Press Ctrl+C to stop\n")
    
    def handle_client(self, client_socket):
        """Handle incoming client connection."""
        try:
            while self.running:
                # Receive message length (4 bytes, little-endian to match backend)
                length_data = client_socket.recv(4)
                if not length_data:
                    break
                
                # Try little-endian first (matches new backend)
                msg_length = struct.unpack('<I', length_data)[0]
                
                # Sanity check - if too large, try big-endian
                if msg_length > 1000000:
                    msg_length = struct.unpack('>I', length_data)[0]
                
                # Receive message
                data = b''
                while len(data) < msg_length:
                    chunk = client_socket.recv(min(4096, msg_length - len(data)))
                    if not chunk:
                        break
                    data += chunk
                
                # Parse JSON
                try:
                    command = json.loads(data.decode('utf-8'))
                    print(f"Received: {command}")
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
                    continue
                
                # Process command
                response = self.process_command(command)
                
                # Send response
                if response.get("image"):
                    image_data = response["image"]
                    # Use little-endian to match backend expectation
                    header = struct.pack('<I', len(image_data))
                    client_socket.sendall(header + image_data)
                else:
                    resp_data = json.dumps(response).encode('utf-8')
                    header = struct.pack('<I', len(resp_data))
                    client_socket.sendall(header + resp_data)
        
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            client_socket.close()
            print("Client disconnected")
    
    def process_command(self, command):
        """Process incoming command - handles both old and new formats."""
        # Support both 'type' (old) and 'action' (new backend) fields
        cmd_type = command.get("action") or command.get("type", "update")
        
        # Handle update_and_render (from new backend)
        if cmd_type == "update_and_render":
            data = command.get("data", {})
            result = update_digital_twin(data)
            
            image_data = render_frame()
            if image_data:
                return {"status": "ok", "image": image_data}
            else:
                return {"status": "error", "message": "Render failed"}
        
        # Handle update (legacy)
        elif cmd_type == "update":
            data = command.get("data", {})
            result = update_digital_twin(data)
            
            if command.get("render", True):
                image_data = render_frame()
                if image_data:
                    return {"status": "ok", "image": image_data}
                else:
                    return {"status": "error", "message": "Render failed"}
            
            return result
        
        # Handle camera commands
        elif cmd_type == "camera":
            camera_action = command.get("camera_action", "")
            
            # Handle rotate commands
            if camera_action == "rotate_left" or camera_action == "left":
                result = rotate_camera("left")
            elif camera_action == "rotate_right" or camera_action == "right":
                result = rotate_camera("right")
            elif camera_action == "rotate_up" or camera_action == "up":
                result = rotate_camera("up")
            elif camera_action == "rotate_down" or camera_action == "down":
                result = rotate_camera("down")
            # Handle preset commands
            elif camera_action.startswith("preset_"):
                preset = camera_action.replace("preset_", "")
                result = set_camera_preset(preset)
            else:
                result = {"status": "ok", "message": f"Unknown camera action: {camera_action}"}
            
            # Render after camera change
            if command.get("render", True):
                image_data = render_frame()
                if image_data:
                    return {"status": "ok", "image": image_data}
            
            return result
        
        # Handle rotate_camera (legacy)
        elif cmd_type == "rotate_camera":
            direction = command.get("direction", "left")
            angle = command.get("angle", 15)
            result = rotate_camera(direction, angle)
            
            if command.get("render", True):
                image_data = render_frame()
                if image_data:
                    return {"status": "ok", "image": image_data}
            
            return result
        
        # Handle zoom_camera
        elif cmd_type == "zoom_camera":
            delta = command.get("delta", 0)
            result = zoom_camera(delta)
            
            if command.get("render", True):
                image_data = render_frame()
                if image_data:
                    return {"status": "ok", "image": image_data}
            
            return result
        
        # Handle set_camera_preset (legacy)
        elif cmd_type == "set_camera_preset":
            preset = command.get("preset", "front")
            result = set_camera_preset(preset)
            
            if command.get("render", True):
                image_data = render_frame()
                if image_data:
                    return {"status": "ok", "image": image_data}
            
            return result
        
        # Handle ping
        elif cmd_type == "ping":
            return {"status": "pong"}
        
        # Handle get_info
        elif cmd_type == "get_info":
            return {
                "status": "ok",
                "controller": CONTROLLER_NAME,
                "turbopump": TURBOPUMP_DRIVER_NAME,
                "render_mode": self.render_mode
            }
        
        else:
            print(f"Unknown command type: {cmd_type}")
            return {"status": "error", "message": f"Unknown command: {cmd_type}"}
    
    def run(self):
        """Main server loop."""
        self.start()
        
        while self.running:
            try:
                client_socket, addr = self.socket.accept()
                print(f"✓ Connected: {addr}")
                self.handle_client(client_socket)
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                print("\nShutting down...")
                self.running = False
        
        self.socket.close()
        print("Server stopped")

# =============================================================================
# MODAL OPERATOR
# =============================================================================

class DigitalTwinServerOperator(bpy.types.Operator):
    """Run Digital Twin Server"""
    bl_idname = "wm.digital_twin_server"
    bl_label = "Digital Twin Server"
    
    _timer = None
    _server = None
    _thread = None
    
    def modal(self, context, event):
        if event.type == 'ESC':
            self.cancel(context)
            return {'CANCELLED'}
        
        if event.type == 'TIMER':
            pass
        
        return {'PASS_THROUGH'}
    
    def execute(self, context):
        setup_render()
        
        self._server = BlenderServer()
        self._thread = threading.Thread(target=self._server.run)
        self._thread.daemon = True
        self._thread.start()
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._server:
            self._server.running = False
        wm = context.window_manager
        wm.event_timer_remove(self._timer)

def register():
    bpy.utils.register_class(DigitalTwinServerOperator)

def unregister():
    bpy.utils.unregister_class(DigitalTwinServerOperator)

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("STARTING BLENDER DIGITAL TWIN SERVER")
    print("="*60)
    
    setup_render()
    
    if bpy.app.background:
        print("Running in BACKGROUND mode")
        print("Using EEVEE render\n")
        
        server = BlenderServer()
        server.render_mode = "eevee"
        server.run()
    else:
        print("Running in INTERACTIVE mode")
        print("Using EEVEE render for reliability\n")
        
        register()
        
        server = BlenderServer()
        server.render_mode = "eevee"
        
        thread = threading.Thread(target=server.run)
        thread.daemon = True
        thread.start()
        
        print("Server running in background thread")
        print("Blender UI is still usable")
        print("Close Blender to stop server")