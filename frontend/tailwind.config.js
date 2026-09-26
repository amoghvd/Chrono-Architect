/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: { extend: { fontFamily: { sans: ['DM Sans', 'sans-serif'], display: ['Manrope', 'sans-serif'], mono: ['DM Mono', 'monospace'] }, colors: { forest: '#087f63', ink: '#182523' } } },
  plugins: [],
};
