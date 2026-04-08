/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        slateDeep: '#0f172a',
        steel: '#334155',
        mint: '#10b981',
        amber: '#f59e0b',
        coral: '#ef4444',
        cloud: '#e2e8f0'
      },
      fontFamily: {
        display: ['Poppins', 'sans-serif'],
        body: ['Manrope', 'sans-serif']
      },
      boxShadow: {
        soft: '0 12px 30px rgba(15, 23, 42, 0.12)'
      },
      keyframes: {
        riseIn: {
          '0%': { opacity: 0, transform: 'translateY(12px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' }
        }
      },
      animation: {
        riseIn: 'riseIn 0.5s ease forwards'
      }
    }
  },
  plugins: []
};
