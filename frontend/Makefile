.PHONY: check export-android build-preview

check:
	npm run check

export-android:
	npm run export:android

build-preview: check export-android
	npx eas-cli@latest build --platform android --profile preview
