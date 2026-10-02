/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#142d2b',
        forest: '#0d5248',
        mint: '#e8f5ee',
        lime: '#cbeb6b',
      },
    },
  },
}
