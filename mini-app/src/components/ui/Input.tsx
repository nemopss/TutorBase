import React from 'react';

interface InputProps {
    label?: string;
    placeholder?: string;
    value: string;
    onChange: (value: string) => void;
    error?: string;
    type?: 'text' | 'email' | 'password' | 'tel';
    required?: boolean;
    autoFocus?: boolean;
    disabled?: boolean;
    className?: string;
}

export const Input: React.FC<InputProps> = ({
    label,
    placeholder,
    value,
    onChange,
    error,
    type = 'text',
    required = false,
    autoFocus = false,
    disabled = false,
    className = '',
}) => {
    return (
        <div className={`input-wrapper ${className}`}>
            {label && (
                <label className="block text-sm font-medium text-gray-700 mb-2">
                    {label}
                    {required && <span className="text-red-500 ml-1">*</span>}
                </label>
            )}

            <input
                type={type}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                required={required}
                autoFocus={autoFocus}
                disabled={disabled}
                className={`
          w-full px-4 py-3 rounded-lg border
          ${error ? 'border-red-500' : 'border-gray-300'}
          ${disabled ? 'bg-gray-100 cursor-not-allowed' : 'bg-white'}
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
          transition-colors duration-200
          text-base
        `}
            />

            {error && (
                <p className="mt-2 text-sm text-red-600">
                    {error}
                </p>
            )}
        </div>
    );
};
