interface StatCardProps {
  label: string;
  tone: string;
  value: number;
}

export default function StatCard({ label, tone, value }: StatCardProps) {
  return (
    <div className="stat-card">
      <div
        className={`pointer-events-none absolute inset-0 bg-gradient-to-br opacity-30 ${tone}`}
      />
      <div className="relative">
        <p className="font-semibold text-muted-foreground text-xs uppercase tracking-[0.24em]">
          {label}
        </p>
        <p className="mt-4 font-semibold text-4xl text-foreground tracking-tight">
          {value}
        </p>
      </div>
    </div>
  );
}
