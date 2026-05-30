/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Police dark theme palette
        navy: {
          950: '#020817',
          900: '#0a0f1e',
          800: '#0f172a',
          700: '#1e293b',
          600: '#334155',
        },
        alert: {
          critical: '#dc2626',
          high:     '#ea580c',
          medium:   '#ca8a04',
          low:      '#16a34a',
        },
      },
      animation: {
        'pulse-red': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in':  'slideIn 0.3s ease-out',
        'fade-in':   'fadeIn 0.4s ease-out',
      },
      keyframes: {
        slideIn: { from: { transform: 'translateX(100%)', opacity: 0 }, to: { transform: 'translateX(0)', opacity: 1 } },
        fadeIn:  { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
