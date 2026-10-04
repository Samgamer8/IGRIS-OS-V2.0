import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: { rolldownOptions: { input: { game: 'index.html', studio: 'studio.html' } } },
});