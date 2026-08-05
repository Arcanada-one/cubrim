#![forbid(unsafe_code)]

use clap::{Args, Parser, Subcommand, ValueEnum};
use cubrim::{EncodeConfig, GapScheme, Preset, ValueScheme};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "cubrim")]
#[command(version, about = "Cubrim lossless compressor and .cbr archiver")]
#[command(
    after_help = "Examples:\n  cubrim compress input.bin input.cub\n  cubrim decompress input.cub restored.bin\n  cubrim a archive.cbr dir file.txt\n  cubrim x archive.cbr -o restored\n  cubrim l archive.cbr\n  cubrim t archive.cbr"
)]
pub struct Cli {
    #[arg(long, help = "Show the Cubrim license terms and exit")]
    pub license: bool,
    #[arg(long, help = "Accept the Cubrim license non-interactively and exit")]
    pub accept_license: bool,
    #[arg(
        long,
        help = "Check for and install the latest stable Cubrim CLI release"
    )]
    pub update: bool,
    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Debug, Subcommand)]
pub enum Commands {
    #[command(alias = "c", about = "Compress one file to a legacy Cubrim blob")]
    Compress(CompressArgs),
    #[command(alias = "d", about = "Decompress one legacy Cubrim blob")]
    Decompress(DecompressArgs),
    #[command(alias = "a", about = "Create a .cbr archive from files or directories")]
    Add(AddArgs),
    #[command(
        alias = "x",
        about = "Extract a .cbr archive, or decompress a legacy blob with two positionals"
    )]
    Extract(ExtractArgs),
    #[command(alias = "l", about = "List a .cbr archive")]
    List(ListArgs),
    #[command(alias = "t", about = "Test a .cbr archive without extracting")]
    Test(TestArgs),
}

#[derive(Debug, Args)]
pub struct CompressArgs {
    pub input: PathBuf,
    pub output: PathBuf,
    #[arg(long)]
    pub raw_store_bound: Option<usize>,
    #[arg(long)]
    pub b: Option<usize>,
    #[arg(long)]
    pub n: Option<usize>,
    #[arg(long, value_enum)]
    pub gap_scheme: Option<GapSchemeArg>,
    #[arg(long, value_enum)]
    pub value_scheme: Option<ValueSchemeArg>,
    #[arg(long)]
    pub min_ctx_count: Option<u16>,
    #[arg(long, value_enum, help = "Speed/ratio operating point (default: max)")]
    pub preset: Option<PresetArg>,
    #[arg(short, long)]
    pub quiet: bool,
}

impl CompressArgs {
    pub fn encode_config(&self) -> EncodeConfig {
        let mut config = EncodeConfig::v1_default();
        // Preset first, so the explicit low-level overrides below still win.
        if let Some(preset) = self.preset {
            config = Preset::from(preset).apply(config);
        }
        if let Some(value) = self.raw_store_bound {
            config.raw_store_bound = value;
        }
        if let Some(value) = self.b {
            config.b = value;
        }
        if let Some(value) = self.n {
            config.n_override = Some(value);
        }
        if let Some(value) = self.gap_scheme {
            config.gap_scheme = value.into();
        }
        if let Some(value) = self.value_scheme {
            config.value_scheme = value.into();
        }
        if let Some(value) = self.min_ctx_count {
            config.min_ctx_count = Some(value);
        }
        config
    }
}

#[derive(Debug, Args)]
pub struct DecompressArgs {
    pub input: PathBuf,
    pub output: PathBuf,
    #[arg(short, long)]
    pub quiet: bool,
}

#[derive(Debug, Args)]
pub struct AddArgs {
    pub archive: PathBuf,
    #[arg(required = true)]
    pub paths: Vec<PathBuf>,
    #[arg(short, long)]
    pub force: bool,
    #[arg(short, long)]
    pub quiet: bool,
    #[arg(long)]
    pub preserve: bool,
    #[arg(short, long, num_args = 0..=1, default_missing_value = "")]
    pub password: Option<String>,
    #[arg(long, value_enum, help = "Speed/ratio operating point (default: max)")]
    pub preset: Option<PresetArg>,
}

impl AddArgs {
    /// Encode configuration for the user-facing archive path.
    ///
    /// Before CUBR-0087 the archive path had no configuration at all —
    /// `archive.rs` called `encode(&data)`, the crate default — so the operating
    /// point was not reachable from `cubrim a`, only from the hidden internal
    /// `compress` subcommand the benchmark uses. A preset the benchmark can
    /// select and the product cannot is not a product feature.
    pub fn encode_config(&self) -> EncodeConfig {
        let mut config = EncodeConfig::v1_default();
        if let Some(preset) = self.preset {
            config = Preset::from(preset).apply(config);
        }
        config
    }
}

#[derive(Debug, Args)]
pub struct ExtractArgs {
    pub input: PathBuf,
    pub output: Option<PathBuf>,
    #[arg(short = 'o', long)]
    pub out_dir: Option<PathBuf>,
    #[arg(short, long)]
    pub force: bool,
    #[arg(short, long)]
    pub quiet: bool,
    #[arg(long)]
    pub preserve: bool,
    #[arg(short, long, num_args = 0..=1, default_missing_value = "")]
    pub password: Option<String>,
}

#[derive(Debug, Args)]
pub struct ListArgs {
    pub archive: PathBuf,
    #[arg(short, long)]
    pub quiet: bool,
    #[arg(short, long, num_args = 0..=1, default_missing_value = "")]
    pub password: Option<String>,
}

#[derive(Debug, Args)]
pub struct TestArgs {
    pub archive: PathBuf,
    #[arg(short, long)]
    pub quiet: bool,
    #[arg(short, long, num_args = 0..=1, default_missing_value = "")]
    pub password: Option<String>,
}

/// Speed/ratio operating point. See `cubrim::Preset` for the measured trade.
#[derive(Copy, Clone, Debug, ValueEnum)]
pub enum PresetArg {
    /// Maximum ratio, whatever it costs. Byte-identical to the v0.3.2 encoder;
    /// 0.189007 on the full 24-file world corpus.
    Max,
    /// Faster encode for a small ratio cost: +0.47% output on the full 24-file
    /// world corpus.
    ///
    /// The speedup is concentrated by data class, not spread across the corpus,
    /// so it is quoted by class rather than as an average — a mean would
    /// describe none of these files. Measured per file, max vs balanced:
    /// 2.5-3.0x on text/xml/database (xml 2.99x, webster 2.81x, dickens 2.77x,
    /// osdb 2.50x, enwik8 2.48x) and NO CHANGE on executables, images and code
    /// (mozilla, ooffice, x-ray, mr 1.00x, samba 0.99x), where the dropped CM2
    /// column-variant passes never run and the output is byte-identical.
    /// Corpus-wide encode throughput 0.0230 -> 0.0378 MiB/s.
    ///
    /// Archives stay readable by every decoder.
    Balanced,
    /// Bounded decoder memory, for wasm32 and other hard-ceiling environments.
    ///
    /// On the full 24-file world corpus, peak decode RSS falls from 12,561 MiB
    /// to 221 MiB — a 56.8x cut, and the figure that decides whether a browser
    /// decoder is possible at all, since wasm32 caps the address space at 4 GiB.
    /// Peak encode RSS falls 18,603 -> 7,007 MiB. Costs +9.32% output
    /// (0.206627 against max 0.189007), still ahead of ppmd 0.228592.
    ///
    /// NOTE: a decoder that predates the table-exponent field CANNOT read these
    /// archives. It fails closed with a decode error rather than returning wrong
    /// bytes, but it cannot open them. `max` and `balanced` archives have no
    /// such restriction and are readable by every decoder.
    Web,
}

impl From<PresetArg> for Preset {
    fn from(value: PresetArg) -> Self {
        match value {
            PresetArg::Max => Preset::Max,
            PresetArg::Balanced => Preset::Balanced,
            PresetArg::Web => Preset::Web,
        }
    }
}

#[derive(Copy, Clone, Debug, ValueEnum)]
pub enum GapSchemeArg {
    Rle,
    #[value(alias = "rle_u16")]
    RleU16,
    #[value(alias = "packed_nibble")]
    PackedNibble,
}

impl From<GapSchemeArg> for GapScheme {
    fn from(value: GapSchemeArg) -> Self {
        match value {
            GapSchemeArg::Rle | GapSchemeArg::RleU16 => GapScheme::RleU16,
            GapSchemeArg::PackedNibble => GapScheme::PackedNibble,
        }
    }
}

#[derive(Copy, Clone, Debug, ValueEnum)]
pub enum ValueSchemeArg {
    #[value(alias = "bitpack_fixed")]
    BitpackFixed,
    #[value(alias = "rle_codes")]
    RleCodes,
    Entropy,
    #[value(alias = "entropy_context")]
    EntropyContext,
    #[value(alias = "entropy_context_2")]
    EntropyContext2,
    #[value(alias = "bwt_entropy", alias = "bwt")]
    BwtEntropy,
    #[value(alias = "bwt_rans", alias = "rans")]
    BwtRans,
    #[value(alias = "order2_rans", alias = "bwt-order2-rans")]
    Order2Rans,
    #[value(alias = "bwt_adaptive", alias = "adaptive")]
    BwtAdaptive,
    #[value(alias = "bwt-ctxmix", alias = "bwt_ctxmix", alias = "ctxmix")]
    BwtCtxmix,
    #[value(alias = "bwt-geomix", alias = "bwt_geomix", alias = "geomix")]
    BwtGeomix,
    #[value(alias = "lz-rans", alias = "lz_rans", alias = "lz")]
    LzRans,
}

impl From<ValueSchemeArg> for ValueScheme {
    fn from(value: ValueSchemeArg) -> Self {
        match value {
            ValueSchemeArg::BitpackFixed => ValueScheme::BitpackFixed,
            ValueSchemeArg::RleCodes => ValueScheme::RleCodes,
            ValueSchemeArg::Entropy => ValueScheme::Entropy,
            ValueSchemeArg::EntropyContext => ValueScheme::EntropyContext,
            ValueSchemeArg::EntropyContext2 => ValueScheme::EntropyContext2,
            ValueSchemeArg::BwtEntropy => ValueScheme::BwtEntropy,
            ValueSchemeArg::BwtRans => ValueScheme::BwtRans,
            ValueSchemeArg::Order2Rans => ValueScheme::Order2Rans,
            ValueSchemeArg::BwtAdaptive => ValueScheme::BwtAdaptive,
            ValueSchemeArg::BwtCtxmix => ValueScheme::BwtContextMix,
            ValueSchemeArg::BwtGeomix => ValueScheme::BwtGeoMix,
            ValueSchemeArg::LzRans => ValueScheme::LzRans,
        }
    }
}
