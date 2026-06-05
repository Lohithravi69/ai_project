import { Badge } from './ui/badge';
import { Progress } from './ui/progress';

export function ScanStatus({ label, progress }: { label: string; progress: number }) {
  return (
    <div className="space-y-2 rounded-3xl border border-white/10 bg-black/20 p-4">
      <div className="flex items-center justify-between gap-4">
        <span className="text-sm text-white/70">{label}</span>
        <Badge>{progress}%</Badge>
      </div>
      <Progress value={progress} />
    </div>
  );
}
