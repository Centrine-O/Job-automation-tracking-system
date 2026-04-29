/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        onyx:  { DEFAULT: '#13140e', dim: '#474a38' },
        olive: { DEFAULT: '#838236', bright: '#9a9a3f' },
        bone:  { DEFAULT: '#dedacf', 1: '#d4d0c5', 2: '#c8c4b9', 3: '#b8b4a9' },
      },
      fontFamily: {
        serif: ['"Crimson Text"', 'Georgia', 'serif'],
        mono:  ['"IBM Plex Mono"', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
