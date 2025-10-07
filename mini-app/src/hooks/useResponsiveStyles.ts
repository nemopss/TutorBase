import { useTelegram } from './useTelegram';

export const useResponsiveStyles = () => {
  const { colorScheme } = useTelegram();

  const cardStyle = {
    background: colorScheme === 'dark' ? '#1f1f1f' : '#ffffff',
    borderColor: colorScheme === 'dark' ? '#3a3a3a' : '#e8e8e8',
  };

  const textColor = colorScheme === 'dark' ? '#ffffff' : '#000000';
  const subtitleColor = colorScheme === 'dark' ? '#a0a0a0' : '#8c8c8c';
  const borderColor = colorScheme === 'dark' ? '#3a3a3a' : '#e8e8e8';
  const chartGridColor = colorScheme === 'dark' ? '#3a3a3a' : '#e8e8e8';

  const tooltipStyle = {
    backgroundColor: cardStyle.background,
    borderColor: cardStyle.borderColor,
    color: textColor,
  };

  return {
    cardStyle,
    textColor,
    subtitleColor,
    borderColor,
    chartGridColor,
    tooltipStyle,
    colorScheme,
  };
};
