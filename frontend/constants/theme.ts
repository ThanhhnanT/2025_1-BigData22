/**
 * Theme constants for trading dashboard
 * Consistent color palette and styling values
 */

export const COLORS = {
  // Background colors
  background: {
    primary: '#111827',
    secondary: '#1f2937',
    tertiary: '#131722',
    hover: '#374151',
  },
  
  // Border colors
  border: {
    primary: '#374151',
    secondary: '#2b3139',
  },
  
  // Text colors
  text: {
    primary: '#fff',
    secondary: '#eaecef',
    muted: '#848e9c',
  },
  
  // Status colors
  status: {
    success: '#10b981',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6',
  },
  
  // Trading colors
  trading: {
    buy: '#10b981',
    sell: '#ef4444',
  },
} as const;

export const SHADOWS = {
  sm: '0 1px 3px rgba(0, 0, 0, 0.1)',
  md: '0 4px 6px rgba(0, 0, 0, 0.1)',
} as const;

export const BORDER_RADIUS = {
  sm: '4px',
  md: '6px',
  lg: '8px',
} as const;
