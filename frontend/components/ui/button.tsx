import type { ButtonHTMLAttributes } from 'react';

import { cn } from '../../lib/cn';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost';
};

export function Button({ className, variant = 'primary', ...props }: ButtonProps) {
  const variants: Record<NonNullable<ButtonProps['variant']>, string> = {
    primary: 'bg-[hsl(var(--accent))] text-black hover:brightness-110',
    secondary: 'bg-white/[0.08] text-white hover:bg-white/[0.12]',
    ghost: 'bg-transparent text-white/80 hover:bg-white/[0.08]',
  };

  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-xl border border-white/10 px-4 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent))] disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
