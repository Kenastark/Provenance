/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_API_KEY?: string;
  /**
   * A MapLibre style URL for the basemap. Unset, the map draws a token-coloured
   * ground with a real graticule and no invented geography. See features/map/mapStyle.ts.
   */
  readonly VITE_MAP_STYLE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
