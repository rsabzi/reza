/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        background: '#05070d',
        surface: '#0b0f1a',
        panel: '#0e1420',
        elevated: '#141b2b',
        line: '#1d2740',
        primary: {
          DEFAULT: '#8b5cf6',
          soft: '#b3a5ff',
          dark: '#7c3aed',
          deep: '#5b21b6',
        },
        mint: '#34d3c3',
        ink: '#eef2ff',
      },
      boxShadow: {
        card: '0 1px 0 rgba(255,255,255,.04) inset, 0 18px 48px rgba(0,0,0,.24)',
        glow: '0 0 0 1px rgba(139,92,246,.18), 0 20px 65px rgba(0,0,0,.32)',
        popover: '0 24px 80px rgba(0,0,0,.5)',
        orb: '0 0 0 1px rgba(179,165,255,.25), 0 0 24px rgba(139,92,246,.45), 0 18px 50px rgba(0,0,0,.5)',
        bubble: '0 8px 28px rgba(0,0,0,.28)',
      },
      fontFamily: {
        sans: ['Vazirmatn', 'Tahoma', 'Arial', 'sans-serif'],
        mono: ['"SFMono-Regular"', 'Consolas', 'Monaco', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn .28s ease-out',
        'slide-up': 'slideUp .3s cubic-bezier(.16,1,.3,1)',
        'slide-left': 'slideLeft .3s cubic-bezier(.16,1,.3,1)',
        'pop-in': 'popIn .35s cubic-bezier(.16,1.4,.3,1)',
        'pulse-soft': 'pulseSoft 2.2s ease-in-out infinite',
        'orb-pulse': 'orbPulse 3s ease-in-out infinite',
        'ring-pulse': 'ringPulse 2.6s ease-out infinite',
        float: 'floatY 5s ease-in-out infinite',
        shimmer: 'shimmer 1.8s linear infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideLeft: {
          from: { opacity: '0', transform: 'translateX(-14px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        popIn: {
          from: { opacity: '0', transform: 'scale(.94) translateY(8px)' },
          to: { opacity: '1', transform: 'scale(1) translateY(0)' },
        },
        pulseSoft: {
          '0%,100%': { opacity: '.55' },
          '50%': { opacity: '1' },
        },
        orbPulse: {
          '0%,100%': { transform: 'scale(1)', opacity: '.85' },
          '50%': { transform: 'scale(1.06)', opacity: '1' },
        },
        ringPulse: {
          '0%': { transform: 'scale(1)', opacity: '.5' },
          '80%,100%': { transform: 'scale(1.9)', opacity: '0' },
        },
        floatY: {
          '0%,100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        shimmer: {
          from: { backgroundPosition: '200% 0' },
          to: { backgroundPosition: '-200% 0' },
        },
      },
    },
  },
  plugins: [],
}
