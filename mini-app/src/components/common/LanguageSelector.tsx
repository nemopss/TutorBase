import React from 'react';
import { Select } from 'antd';
import { GlobalOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { 
  SUPPORTED_LANGUAGES, 
  LANGUAGE_LABELS, 
  LANGUAGE_FLAGS,
  changeLanguage,
  type SupportedLanguage 
} from '../../i18n';

interface LanguageSelectorProps {
  showLabel?: boolean;
  showFlag?: boolean;
  size?: 'small' | 'middle' | 'large';
  style?: React.CSSProperties;
}

const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  showLabel = true,
  showFlag = true,
  size = 'middle',
  style,
}) => {
  const { i18n } = useTranslation();
  
  const currentLanguage = (
    SUPPORTED_LANGUAGES.includes(i18n.language as SupportedLanguage) 
      ? i18n.language 
      : 'ru'
  ) as SupportedLanguage;

  const handleChange = (value: SupportedLanguage) => {
    changeLanguage(value);
  };

  const options = SUPPORTED_LANGUAGES.map((lang) => ({
    value: lang,
    label: (
      <span>
        {showFlag && <span style={{ marginRight: 8 }}>{LANGUAGE_FLAGS[lang]}</span>}
        {showLabel ? LANGUAGE_LABELS[lang] : ''}
      </span>
    ),
  }));

  return (
    <Select
      value={currentLanguage}
      onChange={handleChange}
      options={options}
      size={size}
      style={{ minWidth: showLabel ? 140 : 70, ...style }}
      suffixIcon={<GlobalOutlined />}
    />
  );
};

export default LanguageSelector;
