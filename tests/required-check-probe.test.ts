import { test, expect } from 'vitest';
const value: number = 'intentional required-check probe';
test('required-check validation only', () => expect(value).toBe(1));
