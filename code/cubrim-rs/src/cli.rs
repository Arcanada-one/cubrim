#![forbid(unsafe_code)]

use clap::{ArgAction, Args, Parser, Subcommand};
use cubrim::{EncodeConfig, GapScheme, ValueScheme};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "cubrim")]
#[command(version, about = "Cubrim .cbr archiver")]
#[command(disable_help_subcommand = true)]
#[command(
    after_help = "Examples:\n  cubrim\n  cubrim a project.cbr src docs README.md\n  cubrim x project.cbr -o restored\n  cubrim e project.cbr -o flat\n  cubrim l project.cbr\n  cubrim t project.cbr\n  cubrim d project.cbr '*.tmp'"
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
    #[arg(short = 'q', long, global = true, action = ArgAction::SetTrue)]
    pub quiet: bool,
    #[arg(short = 'v', long, global = true, action = ArgAction::Count)]
    pub verbose: u8,
    #[arg(short = 'y', long, global = true, action = ArgAction::SetTrue)]
    pub yes: bool,
    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Debug, Subcommand)]
pub enum Commands {
    #[command(name = "a", alias = "add", about = "Create a .cbr archive or add paths to it")]
    Add(ArchiveAddArgs),
    #[command(name = "x", alias = "extract", about = "Extract a .cbr archive with full paths")]
    Extract(ExtractArgs),
    #[command(
        name = "e",
        alias = "extract-flat",
        about = "Extract a .cbr archive flat, ignoring stored directory layout"
    )]
    ExtractFlat(ExtractArgs),
    #[command(name = "l", alias = "list", about = "List a .cbr archive")]
    List(ListArgs),
    #[command(name = "t", alias = "test", about = "Test a .cbr archive without extracting")]
    Test(TestArgs),
    #[command(name = "d", alias = "delete", about = "Delete entries from a .cbr archive")]
    Delete(DeleteArgs),
    #[command(name = "compress", hide = true, about = "Internal benchmark blob encoder")]
    InternalCompress(InternalCompressArgs),
    #[command(name = "decompress", hide = true, about = "Internal benchmark blob decoder")]
    InternalDecompress(InternalDecompressArgs),
}

#[derive(Debug, Args, Clone)]
pub struct CommonArgs {
    #[arg(short = 'f', long, action = ArgAction::SetTrue)]
    pub force: bool,
    #[arg(short = 'p', long, num_args = 0..=1, default_missing_value = "")]
    pub password: Option<String>,
    #[arg(from_global)]
    pub quiet: bool,
    #[arg(from_global)]
    pub yes: bool,
    #[arg(long, action = ArgAction::SetTrue)]
    pub preserve: bool,
}

#[derive(Debug, Args)]
pub struct ArchiveAddArgs {
    pub archive: PathBuf,
    #[arg(required = true)]
    pub paths: Vec<PathBuf>,
    #[arg(short = 'r', long, action = ArgAction::SetTrue)]
    pub recursive: bool,
    #[arg(long, default_value_t = 6)]
    pub level: u8,
    #[command(flatten)]
    pub common: CommonArgs,
}

#[derive(Debug, Args)]
pub struct ExtractArgs {
    pub archive: PathBuf,
    #[arg(short = 'o', long)]
    pub out_dir: Option<PathBuf>,
    #[command(flatten)]
    pub common: CommonArgs,
}

#[derive(Debug, Args)]
pub struct ListArgs {
    pub archive: PathBuf,
    #[arg(short = 'p', long, num_args = 0..=1, default_missing_value = "")]
    pub password: Option<String>,
    #[arg(from_global)]
    pub quiet: bool,
}

#[derive(Debug, Args)]
pub struct TestArgs {
    pub archive: PathBuf,
    #[arg(short = 'p', long, num_args = 0..=1, default_missing_value = "")]
    pub password: Option<String>,
    #[arg(from_global)]
    pub quiet: bool,
}

#[derive(Debug, Args)]
pub struct DeleteArgs {
    pub archive: PathBuf,
    #[arg(required = true)]
    pub patterns: Vec<String>,
    #[command(flatten)]
    pub common: CommonArgs,
}

#[derive(Debug, Args)]
pub struct InternalCompressArgs {
    pub input: PathBuf,
    pub output: PathBuf,
    #[arg(long, default_value_t = 6)]
    pub level: u8,
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
    #[arg(from_global)]
    pub quiet: bool,
}

impl InternalCompressArgs {
    pub fn encode_config(&self) -> EncodeConfig {
        let mut config = level_config(self.level);
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
pub struct InternalDecompressArgs {
    pub input: PathBuf,
    pub output: PathBuf,
    #[arg(from_global)]
    pub quiet: bool,
}

pub fn level_config(level: u8) -> EncodeConfig {
    let clamped = level.clamp(1, 9);
    let mut config = EncodeConfig::v1_default();
    config.value_scheme = match clamped {
        1..=2 => ValueScheme::BitpackFixed,
        3..=4 => ValueScheme::Entropy,
        5..=6 => ValueScheme::BwtEntropy,
        7..=8 => ValueScheme::BwtRans,
        _ => ValueScheme::BwtContextMix,
    };
    if clamped >= 8 {
        config.gap_scheme = GapScheme::PackedNibble;
    }
    config
}

#[derive(Copy, Clone, Debug, clap::ValueEnum)]
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

#[derive(Copy, Clone, Debug, clap::ValueEnum)]
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
        }
    }
}
