import { FILE_FORMAT_COLOR } from "../../constants/ingestion";

export function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M7 16a4 4 0 0 1-.88-7.903A5 5 0 1 1 15.9 6L16 6a5 5 0 0 1 1 9.9" />
      <path d="M12 12v9" />
      <path d="m9 15 3-3 3 3" />
    </svg>
  );
}

export function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

export function IconLock() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

export function IconBuilding() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="3" width="16" height="18" rx="1.5" />
      <path d="M9 7h.01M15 7h.01M9 11h.01M15 11h.01M9 15h.01M15 15h.01" />
    </svg>
  );
}

export function IconLayers() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </svg>
  );
}

export function IconPound() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M8 21h10M8 21c1.6-1 2-2.4 2-4v-4M8 13h6M9.5 13c-.3-1.3-1-2.5-1-4a3.5 3.5 0 0 1 6.6-1.6" />
    </svg>
  );
}

export function IconPin() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

export function IconShield() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

export function IconSparkle() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3v4M12 17v4M5 12H1M23 12h-4M6.3 6.3 3.5 3.5M20.5 20.5l-2.8-2.8M17.7 6.3l2.8-2.8M3.5 20.5l2.8-2.8" />
    </svg>
  );
}

export function IconCheckMini() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

export function IconFile() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M9 13h6M9 17h6" />
    </svg>
  );
}

export function FileTypeIcon({ format }) {
  const fill = FILE_FORMAT_COLOR[format];
  return (
    <svg viewBox="0 0 32 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M6 1.5h14.5L30.5 11.5V36a2.5 2.5 0 0 1-2.5 2.5H6A2.5 2.5 0 0 1 3.5 36V4A2.5 2.5 0 0 1 6 1.5Z"
        fill="#FFFFFF"
        stroke="#D8D2C8"
        strokeWidth="1.6"
      />
      <path
        d="M20.5 1.5V9a2.5 2.5 0 0 0 2.5 2.5h7.5"
        fill="#F1ECE4"
        stroke="#D8D2C8"
        strokeWidth="1.6"
      />
      <rect x="2.5" y="22" width="27" height="13" rx="2.5" fill={fill} />
      <text
        x="16"
        y="31.4"
        textAnchor="middle"
        fontSize="8.5"
        fontWeight="700"
        letterSpacing="0.3"
        fill="#FFFFFF"
        fontFamily="Inter, system-ui, sans-serif"
      >
        {format.toUpperCase()}
      </text>
    </svg>
  );
}
