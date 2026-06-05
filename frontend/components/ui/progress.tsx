import type { HTMLAttributes } from 'react';

import { cn } from '../../lib/cn';

export function Progress({ value = 0, className, ...props }: HTMLAttributes<HTMLDivElement> & { value?: number }) {
  return (
    <div className={cn('h-2 overflow-hidden rounded-full bg-white/[0.08]', className)} {...props}>
      <div className="h-full rounded-full bg-[linear-gradient(90deg,hsl(var(--accent)),hsl(var(--accent-2)))] transition-all" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}
