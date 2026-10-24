/* Link/run probe: SDL2 API (sdl2-compat) over SDL-xenon's SDL3. Logs to the xsdk log. */
#include <SDL2/SDL.h>
#include <stdio.h>
int main(int argc, char **argv) {
	(void)argc; (void)argv;
	SDL_version v;
	SDL_GetVersion(&v);
	printf("SDL2 API %d.%d.%d\n", v.major, v.minor, v.patch);
	if (SDL_Init(SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) != 0) {
		printf("SDL_Init failed: %s\n", SDL_GetError());
		return 1;
	}
	printf("controllers: %d\n", SDL_NumJoysticks());
	SDL_Quit();
	return 0;
}
