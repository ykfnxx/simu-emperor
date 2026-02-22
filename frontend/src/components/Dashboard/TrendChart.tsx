import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

// Mock data for now - will be replaced with real data later
const mockData = [
  { turn: 1, treasury: 1000000, happiness: 70, population: 10000000 },
  { turn: 2, treasury: 1050000, happiness: 72, population: 10050000 },
  { turn: 3, treasury: 1020000, happiness: 68, population: 10100000 },
  { turn: 4, treasury: 1100000, happiness: 75, population: 10150000 },
  { turn: 5, treasury: 1150000, happiness: 78, population: 10200000 },
]

export function TrendChart() {
  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={mockData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="turn" />
        <YAxis />
        <Tooltip />
        <Line
          type="monotone"
          dataKey="treasury"
          stroke="#d97706"
          name="Treasury"
        />
        <Line
          type="monotone"
          dataKey="happiness"
          stroke="#059669"
          name="Happiness"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
