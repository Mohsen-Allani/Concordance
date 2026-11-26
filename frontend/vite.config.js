import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Le backend FastAPI n'est pas modifié : en développement comme en
// prévisualisation, Vite relaie /api vers lui. Même origine vue du
// navigateur, donc aucun CORS à configurer côté serveur.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_API_TARGET || 'http://localhost:8000';
  const proxy = { '/api': { target, changeOrigin: true } };

  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    preview: { port: 4173, proxy },
  };
});
