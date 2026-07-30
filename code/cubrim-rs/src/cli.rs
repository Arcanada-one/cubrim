#![forbid(unsafe_code)]

use clap::{Args, Parser, Subcommand, ValueEnum};
use cubrim::{EncodeConfig, GapScheme, ValueScheme};
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
    #[arg(short, long)]
    pub quiet: bool,
}

impl CompressArgs {
    pub fn encode_config(&self) -> EncodeConfig {
        let mut config = EncodeConfig::v1_default();
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
