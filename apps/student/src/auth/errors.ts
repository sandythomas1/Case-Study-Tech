// The accounts service's stable code for an account with a pending deletion.
export const DELETION_PENDING = "account_deletion_pending";

// An HTTP failure from the accounts service. Carries the status and, at most,
// one allowlisted code; never the response body.
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code?: typeof DELETION_PENDING,
  ) {
    super(
      status === 401 ? "Sign in again." : "The request could not be completed.",
    );
  }
}

export const isDeletionPending = (error: unknown) =>
  error instanceof ApiError && error.code === DELETION_PENDING;

export const isUnauthorized = (error: unknown) =>
  error instanceof ApiError && error.status === 401;
