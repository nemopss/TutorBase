import React, { useEffect } from 'react';

interface ToastProps {
    message: string;
    type?: 'success' | 'error' | 'info' | 'warning';
    duration?: number;
    onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({
    message,
    type = 'info',
    duration = 3000,
    onClose,
}) => {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose();
        }, duration);

        return () => clearTimeout(timer);
    }, [duration, onClose]);

    const typeStyles = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500',
        warning: 'bg-yellow-500',
    };

    const icons = {
        success: '✓',
        error: '✕',
        info: 'ℹ',
        warning: '⚠',
    };

    return (
        <div className="fixed bottom-4 left-4 right-4 z-50 flex justify-center animate-slide-up">
            <div
                className={`
          ${typeStyles[type]}
          text-white px-6 py-4 rounded-lg shadow-lg
          flex items-center space-x-3
          max-w-md w-full
        `}
            >
                <span className="text-xl">{icons[type]}</span>
                <span className="flex-1">{message}</span>
                <button
                    onClick={onClose}
                    className="text-white hover:text-gray-200 transition-colors"
                >
                    ✕
                </button>
            </div>
        </div>
    );
};
