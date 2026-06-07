.PHONY: check export-android build-preview

check:
	npm run check

export-android:
	npm run export:android

build-preview: check export-android
	@tmp=$$(mktemp); \
	cp .gitignore $$tmp; \
	trap 'cp $$tmp .gitignore; rm -f $$tmp' EXIT INT TERM; \
	perl -0pi -e 's/^assets\/\*\n?//m' .gitignore; \
	npx eas-cli@latest build --platform android --profile preview
