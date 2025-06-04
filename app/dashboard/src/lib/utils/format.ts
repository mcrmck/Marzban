/**
 * Common formatting utilities
 */

/**
 * Format a number with commas as thousands separators
 */
export const formatNumber = (num: number): string => {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
};

/**
 * Format a date string to a more readable format
 */
export const formatDateString = (date: string | Date): string => {
    const d = new Date(date);
    return d.toLocaleDateString();
};

/**
 * Format a currency amount
 */
export const formatCurrency = (amount: number, currency: string = 'USD'): string => {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency,
    }).format(amount);
};