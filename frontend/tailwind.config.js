/** @type {import('tailwindcss').Config} */
// tailwind.config.js
// Tells Tailwind to scan all JSX files in src/
// so unused CSS is removed from the final build

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",  // scan all files in src/
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
