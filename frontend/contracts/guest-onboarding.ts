import { z } from "zod";
// Private preview API. Guest capabilities grant access only to one core reading.
export const guestBirthSchema = z
  .object({
    birth_date: z.string(),
    birth_time: z.string(),
    birth_place_id: z.string().min(1).max(160),
    consent: z.literal(true),
    lang: z.enum(["en", "tr"]),
  })
  .strict();
export type GuestBirth = z.infer<typeof guestBirthSchema>;
export const guestTokenSchema = z.string().regex(/^[a-f0-9]{64}$/);
export const guestStateSchema = z
  .object({
    status: z.enum(["generating", "ready", "failed"]),
    expires_at: z.string().datetime(),
    section: z
      .object({
        key: z.literal("core_identity"),
        title: z.string(),
        text: z.string(),
      })
      .optional(),
    stage: z.string().optional(),
  })
  .refine(
    (value) => value.status !== "ready" || !!value.section,
    "Ready previews require a core reading",
  );
export type GuestState = z.infer<typeof guestStateSchema>;
