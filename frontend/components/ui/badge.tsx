import type { HTMLAttributes } from 'react';

import { cn } from '../../lib/cn';

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn('inline-flex items-center rounded-full border border-white/10 bg-white/[0.08] px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.22em] text-white/70', className)} {...props} />;
}
