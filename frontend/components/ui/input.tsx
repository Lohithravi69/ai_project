import type { InputHTMLAttributes } from 'react';

import { cn } from '../../lib/cn';

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn('w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/35 focus:border-[hsl(var(--accent))] focus:outline-none', className)} {...props} />;
}
