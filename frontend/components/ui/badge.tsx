import type { HTMLAttributes } from 'react';

import { cn } from '../../lib/cn';

const variants = {
  default: "border-white/10 bg-white/[0.08] text-white/70",
  secondary: "border-blue-500/20 bg-blue-500/10 text-blue-300",
  destructive: "border-red-500/20 bg-red-500/10 text-red-300",
  outline: "border-white/20 bg-transparent text-white/60",
};

export function Badge({ className, variant = "default", ...props }: HTMLAttributes<HTMLSpanElement> & { variant?: keyof typeof variants }) {
  return <span className={cn('inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.22em]', variants[variant] || variants.default, className)} {...props} />;
}
