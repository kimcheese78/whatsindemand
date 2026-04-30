/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        eyebrow: ['12px', { lineHeight: '16px', letterSpacing: '0.06em', fontWeight: '600' }],
        small:   ['13px', { lineHeight: '18px' }],
        meta:    ['14px', { lineHeight: '20px' }],
        body:    ['16px', { lineHeight: '24px' }],
        h2:      ['22px', { lineHeight: '30px', fontWeight: '500' }],
        display: ['36px', { lineHeight: '42px', letterSpacing: '-0.02em', fontWeight: '500' }],
        hero:    ['48px', { lineHeight: '52px', letterSpacing: '-0.02em', fontWeight: '500' }],
      },
      colors: {
        surface: {
          DEFAULT: 'rgb(255 255 255 / 0.05)',
          raised:  'rgb(255 255 255 / 0.07)',
        },
        ink: {
          DEFAULT: 'rgb(255 255 255 / 0.95)',
          muted:   'rgb(255 255 255 / 0.62)',
          faint:   'rgb(255 255 255 / 0.38)',
          ghost:   'rgb(255 255 255 / 0.22)',
        },
        line: {
          DEFAULT: 'rgb(255 255 255 / 0.10)',
          strong:  'rgb(255 255 255 / 0.20)',
          faint:   'rgb(255 255 255 / 0.04)',
        },
        accent: {
          up:   '#4ade80',
          down: '#f87171',
          warn: '#fbbf24',
        },
      },
    },
  },
  plugins: [],
};
