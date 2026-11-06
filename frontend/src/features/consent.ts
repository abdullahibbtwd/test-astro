import { identity } from "../config/identity";

export function acceptBirthDataConsent(
  marketing: boolean,
  acceptedAt = new Date(),
) {
  return {
    consents: {
      birth_data: {
        version: identity.consentVersion,
        accepted_at: acceptedAt.toISOString(),
      },
      marketing,
    },
  };
}

export function withdrawBirthDataConsent(marketing: boolean) {
  return {
    consents: {
      birth_data: null,
      marketing,
    },
  };
}
