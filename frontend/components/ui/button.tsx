import type { ButtonHTMLAttributes } from 'react';

import { cn } from '../../lib/cn';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'outline' | 'destructive';
  size?: 'sm' | 'md';
};

export function Button({ className, variant = 'primary', size = 'md', ...props }: ButtonProps) {
  const variants: Record<string, string> = {
    primary: 'bg-[hsl(var(--accent))] text-black hover:brightness-110',
    secondary: 'bg-white/[0.08] text-white hover:bg-white/[0.12]',
    ghost: 'bg-transparent text-white/80 hover:bg-white/[0.08]',
    outline: 'border border-white/20 bg-transparent text-white/80 hover:bg-white/[0.08]',
    destructive: 'bg-red-500/10 text-red-300 border-red-500/20 hover:bg-red-500/20',
  };
  const sizes: Record<string, string> = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
  };

  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-xl border border-white/10 font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent))] disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant] || variants.primary,
        sizes[size] || sizes.md,
        className,
      )}
      {...props}
    />
  );
}
