// Out-of-engine driver for DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAWaterWaves.h.
// Reads a case file written by test_water_engine.py and prints the header's answers, one value per line, so the
// Python side can compare them with its own implementation of the contract formulas.
//
//   waves N           then N lines: dirx diry wavelength amplitude steepness speed phase
//   mask S minx miny maxx maxy     then S*S integers (row-major, row 0 = miny)
//   fade start end
//   river N           then N lines: x y z halfwidth
//   eval x y t        -> offx offy offz nx ny nz fold        (undisplaced position, masked + faded)
//   height x y t      -> surface height at the fixed XY (inverse displacement)
//   scale x y         -> mask * fade
//   query x y         -> inside surfacez edge flowx flowy
//   bounds            -> minx miny maxx maxy
#include "DAWaterWaves.h"

#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char** argv)
{
	if (argc < 2)
	{
		std::fprintf(stderr, "usage: test_waves <cases>\n");
		return 2;
	}
	std::ifstream In(argv[1]);
	std::vector<FDAWave> Waves;
	std::vector<uint8> Mask;
	std::vector<FVector4> River;
	DAWater::FWaveField Field;
	std::string Cmd;
	std::printf("%d %.17g %.17g %.17g %d\n", DAWater::MaxWaves, DAWater::DefaultFadeStart, DAWater::DefaultFadeEnd,
		DAWater::RiverHeadroom, DAWater::InverseIterations);
	while (In >> Cmd)
	{
		if (Cmd == "waves")
		{
			int N = 0;
			In >> N;
			Waves.assign(N, FDAWave());
			for (FDAWave& W : Waves)
			{
				In >> W.DirX >> W.DirY >> W.Wavelength >> W.Amplitude >> W.Steepness >> W.Speed >> W.Phase;
			}
			Field.Waves = Waves.data();
			Field.NumWaves = N;
			std::printf("%.17g\n", DAWater::MaxFold(Waves.data(), N));
		}
		else if (Cmd == "mask")
		{
			int S = 0;
			In >> S >> Field.MaskMinX >> Field.MaskMinY >> Field.MaskMaxX >> Field.MaskMaxY;
			Mask.assign(static_cast<size_t>(S) * S, 0);
			for (uint8& V : Mask)
			{
				int I = 0;
				In >> I;
				V = static_cast<uint8>(I);
			}
			Field.Mask = S > 0 ? Mask.data() : nullptr;
			Field.MaskSize = S;
		}
		else if (Cmd == "fade")
		{
			In >> Field.FadeStart >> Field.FadeEnd;
		}
		else if (Cmd == "river")
		{
			int N = 0;
			In >> N;
			River.assign(N, FVector4());
			for (FVector4& P : River)
			{
				In >> P.X >> P.Y >> P.Z >> P.W;
			}
		}
		else if (Cmd == "eval")
		{
			double X, Y, T;
			In >> X >> Y >> T;
			const FDAWaveSample S = Field.SampleAt(X, Y, T);
			std::printf("%.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", S.OffsetX, S.OffsetY, S.OffsetZ, S.NormalX, S.NormalY,
				S.NormalZ, S.Fold);
		}
		else if (Cmd == "height")
		{
			double X, Y, T;
			In >> X >> Y >> T;
			std::printf("%.17g\n", Field.HeightAt(X, Y, T));
		}
		else if (Cmd == "scale")
		{
			double X, Y;
			In >> X >> Y;
			std::printf("%.17g\n", Field.ScaleAt(X, Y));
		}
		else if (Cmd == "query")
		{
			double X, Y;
			In >> X >> Y;
			const DAWater::FRiverHit H = DAWater::QueryRiver(River.data(), static_cast<int32>(River.size()), X, Y);
			std::printf("%d %.17g %.17g %.17g %.17g\n", H.bInside ? 1 : 0, H.SurfaceZ, H.EdgeDistance, H.FlowX, H.FlowY);
		}
		else if (Cmd == "bounds")
		{
			double A = 0, B = 0, C = 0, D = 0;
			const bool bOk = DAWater::RiverBounds(River.data(), static_cast<int32>(River.size()), A, B, C, D);
			std::printf("%d %.17g %.17g %.17g %.17g\n", bOk ? 1 : 0, A, B, C, D);
		}
		else
		{
			std::fprintf(stderr, "unknown command %s\n", Cmd.c_str());
			return 2;
		}
	}
	std::printf("WAVES OK\n");
	return 0;
}
