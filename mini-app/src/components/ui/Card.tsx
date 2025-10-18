import React from 'react';

interface CardProps {
    children: React.ReactNode;
    className?: string;
    onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({
    children,
    className = '',
    onClick,
}) => {
    return (
        <div
            onClick={onClick}
            className={`
        bg-white rounded-lg shadow-sm border border-gray-200
        ${onClick ? 'cursor-pointer' : ''}
        ${className}
      `}
        >
            {children}
        </div>
    );
};
