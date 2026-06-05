import type { TextareaHTMLAttributes } from 'react';

import { cn } from '../../lib/cn';

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn('min-h-[120px] w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-white placeholder:text-white/35 focus:border-[hsl(var(--accent))] focus:outline-none', className)} {...props} />;
}
