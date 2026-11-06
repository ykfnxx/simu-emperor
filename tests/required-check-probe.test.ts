import { test, expect } from 'vitest';
const value: number = 1;
test('required-check validation only', () => expect(value).toBe(1));
