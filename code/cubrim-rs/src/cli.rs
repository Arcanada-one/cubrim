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
    /// Maximum ratio. Byte-identical to the shipped v0.3.2 encoder.
    Max,
    /// Drops the CM2 column-variant passes. Corpus cost is +0.47% output
    /// (24-file world corpus, ratio 0.189891 against max 0.189007); the speedup
    /// is class-dependent and largest where CM2 wins, e.g. 3.00x faster encode
    /// on dickens. Archives stay decodable by every other preset.
    Balanced,
    /// Bounded decoder memory for wasm32 and other hard-ceiling environments:
    /// decode peak 12.27 GiB -> 0.216 GiB on the 24-file world corpus, a 56.8x
    /// cut. Corpus cost is +9.32% output (ratio 0.206627), which is higher than
    /// a small-file measurement suggests: a 2 MB sample derives a 24-bit table
    /// exponent, so capping at 20 costs four steps, while a corpus file of
    /// 16 MB or more derives 27 and pays seven. Still ahead of ppmd (0.228592).
    /// Needs a decoder that reads the table-exponent field; older decoders fail
    /// closed on these archives rather than returning wrong bytes.
    /// (Named `web` before any release shipped the flag; renamed because the
    /// preset states a mechanism — bounded decode memory — while "web" named a
    /// separate product area.)
    LowmemDecode,
}

impl From<PresetArg> for Preset {
    fn from(value: PresetArg) -> Self {
        match value {
            PresetArg::Max => Preset::Max,
            PresetArg::Balanced => Preset::Balanced,
            PresetArg::LowmemDecode => Preset::LowmemDecode,
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
