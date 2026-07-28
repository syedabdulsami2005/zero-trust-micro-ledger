/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      colors: {
        // ── Canvas & Surfaces ──
        canvas:  '#F8F9FA',
        surface: {
          DEFAULT: '#FFFFFF',
          warm:    '#FEFEFE',
          subtle:  '#F3F4F6',
          muted:   '#EBEDF0',
        },
        // ── Typography ──
        ink: {
          DEFAULT:   '#111827',
          secondary: '#374151',
          muted:     '#6B7280',
          faint:     '#9CA3AF',
          ghost:     '#D1D5DB',
        },
        // ── Borders ──
        line: {
          DEFAULT: '#E5E7EB',
          strong:  '#D1D5DB',
          focus:   '#0D9488',
        },
        // ── Primary Accent: Refined Teal ──
        accent: {
          DEFAULT: '#0D9488',
          mid:     '#14B8A6',
          light:   '#2DD4BF',
          faint:   '#F0FDFA',
          hover:   '#0F766E',
          deep:    '#134E4A',
        },
        // ── Status Semantic ──
        ok: {
          DEFAULT: '#059669',
          bg:      '#ECFDF5',
          border:  '#A7F3D0',
        },
        warn: {
          DEFAULT: '#D97706',
          bg:      '#FFFBEB',
          border:  '#FDE68A',
        },
        danger: {
          DEFAULT: '#DC2626',
          bg:      '#FEF2F2',
          border:  '#FECACA',
        },
        info: {
          DEFAULT: '#2563EB',
          bg:      '#EFF6FF',
          border:  '#BFDBFE',
        },
        // ── Gold / Premium ──
        gold: {
          DEFAULT: '#B45309',
          bg:      '#FFFBEB',
          border:  '#FDE68A',
          faint:   '#FFFBEB',
        },
      },

      // ── Border Radius ──
      borderRadius: {
        xs:  '4px',
        sm:  '6px',
        md:  '8px',
        lg:  '12px',
        xl:  '16px',
        '2xl': '20px',
        '3xl': '24px',
      },

      // ── Box Shadows ──
      boxShadow: {
        xs:           '0 1px 2px 0 rgba(0,0,0,.04)',
        sm:           '0 1px 3px 0 rgba(0,0,0,.06), 0 1px 2px -1px rgba(0,0,0,.04)',
        card:         '0 1px 4px 0 rgba(0,0,0,.05), 0 1px 2px -1px rgba(0,0,0,.03)',
        'card-md':    '0 4px 14px -2px rgba(0,0,0,.06), 0 2px 6px -2px rgba(0,0,0,.04)',
        'card-lg':    '0 12px 32px -6px rgba(0,0,0,.08), 0 4px 10px -4px rgba(0,0,0,.04)',
        'card-hover': '0 12px 28px -6px rgba(13,148,136,.14), 0 4px 10px -4px rgba(0,0,0,.05)',
        'btn-accent': '0 2px 8px 0 rgba(13,148,136,.28)',
      },

      // ── Animations ──
      animation: {
        'fade-in':     'fadeIn 0.20s ease-out both',
        'slide-up':    'slideUp 0.26s cubic-bezier(0.16,1,0.3,1) both',
        'slide-in':    'slideIn 0.26s cubic-bezier(0.16,1,0.3,1) both',
        'scale-in':    'scaleIn 0.18s ease-out',
        'pulse-slow':  'pulse 2.5s cubic-bezier(0.4,0,0.6,1) infinite',
        'shimmer':     'shimmer 2s linear infinite',
        'float':       'float 3.5s ease-in-out infinite',
        'bounce-subtle': 'bounceSubtle 2s ease-in-out infinite',
      },

      keyframes: {
        fadeIn:       { '0%': { opacity: '0', transform: 'translateY(-4px)' },  '100%': { opacity: '1', transform: 'translateY(0)' } },
        slideUp:      { '0%': { opacity: '0', transform: 'translateY(12px)' },  '100%': { opacity: '1', transform: 'translateY(0)' } },
        slideIn:      { '0%': { opacity: '0', transform: 'translateX(14px)' },  '100%': { opacity: '1', transform: 'translateX(0)' } },
        scaleIn:      { '0%': { opacity: '0', transform: 'scale(0.95)' },        '100%': { opacity: '1', transform: 'scale(1)' } },
        shimmer:      { '0%': { backgroundPosition: '-200% 0' },                  '100%': { backgroundPosition: '200% 0' } },
        float:        { '0%,100%': { transform: 'translateY(0)' },               '50%': { transform: 'translateY(-4px)' } },
        bounceSubtle: { '0%,100%': { transform: 'translateY(0)' },               '50%': { transform: 'translateY(-2px)' } },
      },

      transitionTimingFunction: {
        spring: 'cubic-bezier(0.16, 1, 0.3, 1)',
        smooth: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
        bounce: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },

      transitionDuration: {
        '110': '110ms',
        '200': '200ms',
        '340': '340ms',
      },
    },
  },
  plugins: [],
}
