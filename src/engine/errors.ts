export class DomainError extends Error {
  public readonly status: 400 | 401 | 403 | 404 | 409;
  public readonly code: string;

  constructor(status: 400 | 401 | 403 | 404 | 409, code: string, message: string) {
    super(message);
    this.name = 'DomainError';
    this.status = status;
    this.code = code;
  }
}
