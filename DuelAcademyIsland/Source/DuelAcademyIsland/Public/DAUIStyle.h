// Duel Academy Island - shared Canvas UI palette.
//
// The gameplay screens (shop, deck editor, exam) use exactly these values.
// The HUD, dialogue, PDA and title screen keep their own slightly different
// Ink/Muted tones locally; only switch a screen here when its values match.
//
// Header-only and namespaced so unity builds never see two file-static
// definitions of the same name.

#pragma once

#include "CoreMinimal.h"

namespace DAUIStyle
{
	inline const FLinearColor Gold(1.f, 0.78f, 0.25f);
	inline const FLinearColor Ink(0.008f, 0.014f, 0.028f);
	inline const FLinearColor Paper(0.95f, 0.95f, 0.97f);
	inline const FLinearColor Muted(0.58f, 0.63f, 0.72f);
	inline const FLinearColor Cyan(0.35f, 0.82f, 0.92f);
	inline const FLinearColor Green(0.42f, 0.82f, 0.48f);
	inline const FLinearColor Red(0.90f, 0.28f, 0.24f);
	inline const FLinearColor Purple(0.72f, 0.44f, 0.95f);

	/** Copy of C with its alpha replaced. */
	inline FLinearColor WithAlpha(FLinearColor C, float A)
	{
		C.A = A;
		return C;
	}
}
