import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface GraphPoint {
  cycle: number;
  drul: number;
}

interface RULGraphProps {
  data: GraphPoint[];
}

export const RULGraph = ({ data }: RULGraphProps) => {
  // DEBUG: Print data length to console on every render
  console.log("Graph Component Rendered. Data Points:", data?.length);

  if (!data || data.length === 0) {
    return (
      <div className="w-full h-[300px] bg-card p-4 rounded-lg border border-border shadow-sm mt-4 flex flex-col justify-center items-center text-muted-foreground">
        <h3 className="text-sm font-semibold mb-2 text-foreground">Degradation Rate (dRUL)</h3>
        <p>Waiting for data... (0 points)</p>
      </div>
    );
  }

  return (
    <div className="w-full h-[300px] bg-card p-4 rounded-lg border border-border shadow-sm mt-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-semibold text-foreground">Degradation Rate (dRUL)</h3>
        <span className="text-xs text-muted-foreground">Live Updates</span>
      </div>
      
      <div className="w-full h-[230px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            
            {/* X-AXIS: Hidden ticks and labels */}
            <XAxis 
              dataKey="cycle" 
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={false}       // Hides the numbers on the axis
              axisLine={true}    // Keeps the bottom line visible
              stroke="#888"
            />

            <YAxis 
              domain={['auto', 'auto']}
              label={{ value: 'dRUL', angle: -90, position: 'insideLeft', fill: '#888', fontSize: 12 }} 
              stroke="#888"
              tick={{ fill: '#888', fontSize: 12 }}
            />
            
            <Tooltip 
              contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#fff' }}
              // FIX: This hides the Cycle number (header) from the tooltip completely
              labelStyle={{ display: 'none' }} 
              formatter={(value: number) => [value.toFixed(4), 'dRUL']}
            />
            
            <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
            
            <Line 
              type="monotone" 
              dataKey="drul" 
              stroke="#ef4444" 
              strokeWidth={2}
              dot={false}
              isAnimationActive={false} 
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};