# Ocarina of Time no Xbox 360

Port homebrew de **The Legend of Zelda: Ocarina of Time** para Xbox 360, feito a partir do
[Ship of Harkinian](https://github.com/HarbourMasters/Shipwright) 9.3.1 e da libultraship, com um renderizador novo
para o Xenos e o [xsdk](https://github.com/xenosworks).

*Homebrew port of Ocarina of Time to the Xbox 360, based on Ship of Harkinian 9.3.1. It needs a console that runs
unsigned code (RGH/JTAG) and your own ROM. English details are in [docs/PLAYING.md](docs/PLAYING.md) and
[docs/STATUS.md](docs/STATUS.md).*

> **Estado: em desenvolvimento, sem versão lançada.** O teste 26 é o candidato à 1.0: é o teste 25, que está rodando bem no console mas ainda sem log analisado, com os créditos, testados só no Xenia.

## O que este repositório tem

Só o código do port: os patches sobre o Ship of Harkinian e a libultraship, o script de build e as ferramentas.
**Não há ROM, dados do jogo, traduções nem pacotes de textura aqui.** Não abra issues nem pull requests com esses
arquivos.

## O que já foi testado

- Em um Xbox 360 RGH com HD interno: tela título, seleção de arquivo, jogo em 720p, texto em português, pacote HD e
  modelos do 3DS (testes 5 a 24c). Os resultados de cada teste estão em [docs/STATUS.md](docs/STATUS.md).
- Os 60 fps não são estáveis em todas as áreas. Na Floresta Kokiri, o teste 24c gastou cerca de 27 ms por quadro. O teste
  25 tem correções para isso, mas o ganho ainda não foi medido.
- O jogo inteiro nunca foi jogado do começo ao fim neste port.
- Só um console foi testado, e o build nunca foi refeito em outra máquina.

## Faltando

Leitura de profundidade (clarão das lentes desligado), MSAA, opção 4:3 e FOV para widescreen.

## O que você precisa

- Um Xbox 360 que rode código não assinado (RGH ou JTAG).
- Sua própria ROM NTSC-U 1.0, para gerar os dados no PC com o Ship of Harkinian 9.3.1.

O passo a passo, incluindo a tradução em português e os pacotes HD opcionais, está em [docs/PLAYING.md](docs/PLAYING.md).

## Como compilar

Precisa do toolchain xsdk (`xsdk`, `xsdk-gcc`, `SDL-xenon` e `glslang-xenon`) em uma pasta só:

```bash
XSDK_HOME=/caminho/do/toolchain WORK=~/oot360-work JOBS=4 platform/xbox360/build.sh
```

O script baixa as versões certas do Ship of Harkinian e da libultraship e aplica os patches de
`platform/xbox360/patches`. Antes de commitar, ative a proteção contra dados de jogo:

```bash
git config core.hooksPath tools/hooks
```

## Licença e créditos

A licença do código próprio deste projeto **ainda não foi definida**. O código do jogo, por vir de decompilação, não é
coberto por nenhuma licença deste repositório, e o Ship of Harkinian não publica um arquivo de licença.

Port para Xbox 360 por **Matherzin**. Créditos da base: HarbourMasters (Ship of Harkinian e libultraship), equipe da decompilação zeldaret/oot, xenosworks (xsdk).
As licenças das outras dependências estão listadas em [docs/STATUS.md](docs/STATUS.md).

Projeto de fãs, sem vínculo com a Nintendo ou a Microsoft. The Legend of Zelda é marca da Nintendo.
