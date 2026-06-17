import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
         PieChart, Pie, Cell, Legend } from 'recharts'

const COLORS = {
  low: '#2fd07a',
  medium: '#ffb627',
  high: '#ff5a6e',
  critical: '#ff2040',
  unset: '#5d6b7d',
  open: '#34e1e8',
  closed: '#5d6b7d',
}

const tooltipStyle = {
  backgroundColor: '#151b24',
  border: '1px solid #28323f',
  borderRadius: 6,
  color: '#e8eef5',
  fontSize: '0.78rem',
  fontFamily: "'JetBrains Mono', monospace",
}

export function WOTimeline({ data }) {
  if (!data || data.length === 0) return <p className="muted center" style={{ padding: 14 }}>No timeline data yet.</p>
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <XAxis dataKey="date" tick={{ fill: '#8a99ab', fontSize: 10, fontFamily: "'JetBrains Mono'" }}
          tickFormatter={d => d.slice(5)} />
        <YAxis allowDecimals={false} tick={{ fill: '#8a99ab', fontSize: 10 }} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="open" stackId="a" fill={COLORS.open} name="Open" radius={[0, 0, 0, 0]} />
        <Bar dataKey="closed" stackId="a" fill={COLORS.closed} name="Closed" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function SeverityPie({ data }) {
  if (!data || data.length === 0) return <p className="muted center" style={{ padding: 14 }}>No severity data yet.</p>
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%"
          outerRadius={75} innerRadius={40} paddingAngle={3}
          label={({ name, value }) => `${name} (${value})`}
          labelLine={{ stroke: '#5d6b7d' }}
          style={{ fontSize: '0.72rem', fontFamily: "'JetBrains Mono'" }}>
          {data.map((entry, i) => (
            <Cell key={i} fill={COLORS[entry.name] || '#5d6b7d'} stroke="none" />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: '0.72rem', fontFamily: "'JetBrains Mono'" }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
