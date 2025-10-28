import CandlestickChart from "@/components/charts/CandlestickChart";
import { Card, CardContent } from "@/components/ui/card";

export default function Home() {
  return (
    <main className="min-h-screen p-6 bg-gray-50">
      <h1 className="text-2xl font-semibold mb-4">Crypto Dashboard</h1>
      <Card>
        <CardContent>
          <CandlestickChart />
        </CardContent>
      </Card>
    </main>
  );
}
