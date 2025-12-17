import React from 'react';
import { CheckOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import type { ThemeConfig, ThemeId } from '../../theme/types';
import { allThemeIds, themes } from '../../theme/themes';

interface ThemeCardProps {
  theme: ThemeConfig | null; // null for 'auto'
  themeId: ThemeId;
  isSelected: boolean;
  onClick: () => void;
}

const ThemeCard: React.FC<ThemeCardProps> = ({ theme, themeId, isSelected, onClick }) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();

  // For auto theme, show resolved theme's preview colors and background
  const displayTheme = theme ?? resolvedTheme;
  const previewColors = displayTheme.previewColors;
  const previewBg = displayTheme.colors.bgPrimary;

  const themeName = t(`pages.settings.themes.${themeId}`);

  return (
    <div
      onClick={onClick}
      style={{
        padding: 12,
        borderRadius: 8,
        border: isSelected
          ? `2px solid ${resolvedTheme.colors.accentPrimary}`
          : `1px solid ${resolvedTheme.colors.borderPrimary}`,
        backgroundColor: resolvedTheme.colors.bgSecondary,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        position: 'relative',
      }}
    >
      {/* Selection indicator */}
      {isSelected && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            width: 20,
            height: 20,
            borderRadius: '50%',
            backgroundColor: resolvedTheme.colors.accentPrimary,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <CheckOutlined style={{ color: '#fff', fontSize: 12 }} />
        </div>
      )}

      {/* Color preview */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 4,
          marginBottom: 8,
          padding: 8,
          borderRadius: 6,
          backgroundColor: previewBg,
          border: `1px solid ${resolvedTheme.colors.borderSecondary}`,
          overflow: 'hidden',
        }}
      >
        {previewColors.slice(0, 3).map((color, index) => (
          <div
            key={index}
            style={{
              width: 16,
              height: 16,
              minWidth: 16,
              flexShrink: 0,
              borderRadius: '50%',
              backgroundColor: color,
              border: '1px solid rgba(128,128,128,0.3)',
            }}
          />
        ))}
      </div>

      {/* Theme name */}
      <div
        style={{
          fontSize: 12,
          fontWeight: 500,
          color: resolvedTheme.colors.textPrimary,
          textAlign: 'center',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {themeName}
      </div>
    </div>
  );
};

const ThemeSelector: React.FC = () => {
  const { themeId, setThemeId } = useTheme();

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
        gap: 10,
      }}
    >
      {allThemeIds.map((id) => (
        <ThemeCard
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
