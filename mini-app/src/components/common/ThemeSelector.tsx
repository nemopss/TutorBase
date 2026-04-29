import React from 'react';
import { CheckOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import type { ThemeConfig, ThemeId } from '../../theme/types';
import { themes } from '../../theme/themes';

interface ThemeOptionProps {
  theme: ThemeConfig | null;
  themeId: ThemeId;
  isSelected: boolean;
  onClick: () => void;
}

interface ThemePreviewPalette {
  background: string;
  surface: string;
  surfaceAlt: string;
  text: string;
  muted: string;
  accent: string;
  accentAlt: string;
}

const previewPalettes: Partial<Record<ThemeId, ThemePreviewPalette>> = {
  light: {
    background: '#ffffff',
    surface: '#f7f7f5',
    surfaceAlt: '#ececea',
    text: '#37352f',
    muted: '#b7b4ad',
    accent: '#2383e2',
    accentAlt: '#0f7b6c',
  },
  aqua: {
    background: '#f0fdff',
    surface: '#dff8fb',
    surfaceAlt: '#c4f1f6',
    text: '#164e63',
    muted: '#67c6d1',
    accent: '#00b4d8',
    accentAlt: '#06d6a0',
  },
  dark: {
    background: '#191919',
    surface: '#232323',
    surfaceAlt: '#2f2f2f',
    text: '#f8f8f8',
    muted: '#777777',
    accent: '#2383e2',
    accentAlt: '#0f7b6c',
  },
  darkplus: {
    background: '#1e1e1e',
    surface: '#252526',
    surfaceAlt: '#333333',
    text: '#d4d4d4',
    muted: '#6a9955',
    accent: '#0078d4',
    accentAlt: '#ce9178',
  },
  gruvbox: {
    background: '#282828',
    surface: '#32302f',
    surfaceAlt: '#3c3836',
    text: '#d5c6a0',
    muted: '#a89984',
    accent: '#fe8019',
    accentAlt: '#b8bb26',
  },
  tokyonight: {
    background: '#1f202e',
    surface: '#24283b',
    surfaceAlt: '#292f44',
    text: '#a9b1d6',
    muted: '#565f89',
    accent: '#7dcfff',
    accentAlt: '#bb9af7',
  },
};

const getPreviewPalette = (themeId: ThemeId, displayTheme: ThemeConfig): ThemePreviewPalette => {
  if (themeId === 'auto') {
    return {
      background: displayTheme.colorScheme === 'dark' ? '#191919' : '#ffffff',
      surface: displayTheme.colorScheme === 'dark' ? '#242424' : '#f7f7f5',
      surfaceAlt: displayTheme.colorScheme === 'dark' ? '#303030' : '#e8f6f8',
      text: displayTheme.colorScheme === 'dark' ? '#f8f8f8' : '#37352f',
      muted: displayTheme.colorScheme === 'dark' ? '#777777' : '#9fb7bd',
      accent: '#2383e2',
      accentAlt: '#00b4d8',
    };
  }

  return previewPalettes[themeId] ?? {
    background: displayTheme.colors.bgPrimary,
    surface: displayTheme.colors.bgSecondary,
    surfaceAlt: displayTheme.colors.bgTertiary,
    text: displayTheme.colors.textPrimary,
    muted: displayTheme.colors.textTertiary,
    accent: displayTheme.colors.accentPrimary,
    accentAlt: displayTheme.colors.accentSuccess,
  };
};

const ThemeOption: React.FC<ThemeOptionProps> = ({ theme, themeId, isSelected, onClick }) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const displayTheme = theme ?? resolvedTheme;
  const preview = getPreviewPalette(themeId, displayTheme);
  const themeName = t(`pages.settings.themes.${themeId}`);

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isSelected}
      style={{
        width: '100%',
        display: 'grid',
        gridTemplateColumns: '72px 1fr 20px',
        alignItems: 'center',
        gap: 12,
        padding: 10,
        border: 0,
        borderRadius: 10,
        background: isSelected ? resolvedTheme.colors.bgTertiary : 'transparent',
        color: resolvedTheme.colors.textPrimary,
        cursor: 'pointer',
        textAlign: 'left',
      }}
    >
      <span
        aria-hidden
        style={{
          height: 44,
          borderRadius: 8,
          background: preview.background,
          padding: 6,
          display: 'grid',
          gap: 4,
          boxShadow: `inset 0 0 0 1px ${preview.surfaceAlt}`,
        }}
      >
        <span
          style={{
            height: 7,
            borderRadius: 4,
            background: `linear-gradient(90deg, ${preview.accent} 0 38%, ${preview.surface} 38% 100%)`,
            display: 'block',
          }}
        />
        <span style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, minHeight: 20 }}>
          <span
            style={{
              borderRadius: 5,
              background: preview.surface,
              display: 'grid',
              alignContent: 'center',
              gap: 3,
              padding: '4px 5px',
            }}
          >
            <span style={{ height: 3, borderRadius: 3, background: preview.text, opacity: 0.82 }} />
            <span style={{ height: 3, width: '68%', borderRadius: 3, background: preview.muted }} />
          </span>
          <span
            style={{
              borderRadius: 5,
              background: preview.surfaceAlt,
              display: 'grid',
              gridTemplateColumns: '7px 1fr',
              gap: 4,
              padding: 4,
            }}
          >
            <span style={{ borderRadius: 4, background: preview.accentAlt }} />
            <span style={{ borderRadius: 4, background: preview.accent, opacity: 0.86 }} />
          </span>
        </span>
      </span>
      <span>
        <span style={{ display: 'block', fontWeight: 600 }}>{themeName}</span>
      </span>
      <span style={{
        width: 20,
        height: 20,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: isSelected ? resolvedTheme.colors.textPrimary : 'transparent',
      }}>
        <CheckOutlined style={{ fontSize: 13 }} />
      </span>
    </button>
  );
};

const ThemeSelector: React.FC = () => {
  const { themeId, setThemeId } = useTheme();
  const themeOrder: ThemeId[] = ['auto', 'light', 'aqua', 'dark', 'darkplus', 'gruvbox', 'tokyonight'];

  return (
    <div style={{ display: 'grid', gap: 4 }}>
      {themeOrder.map((id) => (
        <ThemeOption
          key={id}
          themeId={id}
          theme={id === 'auto' ? null : themes[id]}
          isSelected={themeId === id}
          onClick={() => setThemeId(id)}
        />
      ))}
    </div>
  );
};

export default ThemeSelector;
