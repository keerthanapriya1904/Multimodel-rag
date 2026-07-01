// postcss.config.js
// PostCSS processes the CSS — Tailwind needs this to work
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},  // adds -webkit- prefixes for browser compatibility
  },
}
