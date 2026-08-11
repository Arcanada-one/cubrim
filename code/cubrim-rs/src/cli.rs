#![forbid(unsafe_code)]

use clap::{ArgAction, Args, Parser, Subcommand};
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
