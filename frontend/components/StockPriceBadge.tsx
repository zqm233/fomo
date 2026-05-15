import { StockPrice } from "@/lib/api";
import { cn } from "@/lib/utils";
import { TrendingDown, TrendingUp } from "lucide-react";

interface Props {
  stock: StockPrice;
  className?: string;
}

export function StockPriceBadge({ stock, className }: Props) {
  const up = stock.change_pct >= 0;
  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-lg border text-sm",
        up
          ? "border-green-500/30 bg-green-500/5"
          : "border-red-500/30 bg-red-500/5",
        className
      )}
    >
      <span className="font-mono font-bold text-foreground">{stock.symbol}</span>
      <span className="text-muted-foreground text-xs hidden sm:inline">{stock.name}</span>
      <span className="font-mono ml-auto">${stock.price.toFixed(2)}</span>
      <span
        className={cn(
          "flex items-center gap-0.5 font-mono text-xs font-semibold",
          up ? "text-green-400" : "text-red-400"
        )}
      >
        {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
        {up ? "+" : ""}{stock.change_pct.toFixed(2)}%
      </span>
    </div>
  );
}
