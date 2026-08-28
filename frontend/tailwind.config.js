/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        background: '#070910',
        surface: '#0d111b',
        panel: '#111827',
        elevated: '#171f2e',
        line: '#202a3a',
        primary: {
          DEFAULT: '#7c5cff',
          soft: '#a99aff',
          dark: '#6244e8',
        },
        mint: '#2dd4bf',
        ink: '#eef2ff',
      },
      boxShadow: {
        card: '0 1px 0 rgba(255,255,255,.03) inset, 0 18px 48px rgba(0,0,0,.22)',
        glow: '0 0 0 1px rgba(124,92,255,.16), 0 20px 65px rgba(0,0,0,.30)',
        popover: '0 24px 80px rgba(0,0,0,.48)',
      },
      fontFamily: {
        sans: ['Vazirmatn', 'Tahoma', 'Arial', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn .22s ease-out',
        'slide-up': 'slideUp .25s ease-out',
        'pulse-soft': 'pulseSoft 2.2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        pulseSoft: { '0%,100%': { opacity: '.55' }, '50%': { opacity: '1' } },
      },
    },
  },
  plugins: [],
}
