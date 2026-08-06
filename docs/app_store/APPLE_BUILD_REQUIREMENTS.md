# AIGC Apple Build Requirements

Status: APP STORE READINESS PLAN — NOT A BUILD RECEIPT

Reviewed: 2026-08-06

## Submission baseline

- Xcode minimum for App Store Connect upload: 26 or later.
- iOS SDK minimum for App Store Connect upload: iOS 26 or later.
- Swift language mode target: Swift 6.
- Swift strict concurrency: required for project-owned Swift code.
- Production submission authority: false.

Apple reference: https://developer.apple.com/app-store/submitting/

## Proposed product baseline

The actual minimum deployment target is deliberately TBD until the native iOS foundation exists and device-support requirements are measured. The upload SDK requirement is independent of the app's minimum deployment target.

- Minimum deployment target: TBD
- Supported device classes: TBD
- Orientation policy: TBD
- Architecture: arm64 for physical iOS devices; simulator architecture determined by Xcode environment.
- App name: TBD
- Bundle identifier: TBD

## Release signing prerequisites

Before a signed release can be represented as ready:

1. Active Apple Developer Program membership is verified.
2. App identifier and exact bundle identifier are registered.
3. App Store Connect record exists.
4. Entitlements match implemented capability use.
5. Distribution signing is configured through an approved Apple signing workflow.
6. A supported macOS host runs Xcode 26 or later.
7. The exact archive is built and validated.
8. Privacy manifests and required-reason API declarations are derived from the shipped executable and dependencies.
9. Export-compliance and age-rating questions are answered truthfully.
10. TestFlight smoke validation passes before App Store submission.

No certificate, provisioning profile, App Store API key, or production entitlement belongs in Git.
