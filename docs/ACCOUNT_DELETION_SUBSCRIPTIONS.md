# Account deletion and subscriptions

When a user deletes their account (`DELETE /me`):

1. Our servers remove their `subscriptions` and `payment_events` rows (and the rest of the account data).
2. **We do not cancel the App Store or Google Play subscription.** Billing continues until the user cancels in the store.

## What the user must do

- **iOS:** Settings → Apple ID → Subscriptions → cancel the app’s subscription.
- **Android:** Play Store → Payments & subscriptions → Subscriptions → cancel.

The in-app Privacy / delete-account copy (`deleteSubscriptionNote`) states this obligation in EN and TR.

## Why

Apple and Google own the billing relationship. Server-side account wipe cannot stop renewals. After deletion, webhook events for a deleted `user_id` are recorded but do not recreate entitlements (`missing_user` path).
