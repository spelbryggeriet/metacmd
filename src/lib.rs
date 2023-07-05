use std::{
    fmt::{self, Display, Formatter},
    io::{self, Read},
    process as std_process,
};

fn process_cmd_str(s: &str) -> Result<(String, Vec<String>), Error> {
    let mut items = vec![];
    let mut current_item = items.last_mut();

    let mut quote_type: Option<char> = None;
    let mut is_escaping = false;
    for c in s.chars() {
        let is_escape = c == '\\';
        let is_double_quote = c == '"';
        let is_space = c.is_ascii_whitespace();

        let some_current_item = if let Some(some_current_item) = current_item.as_mut() {
            some_current_item
        } else {
            if is_space {
                continue;
            }

            items.push(String::new());
            current_item = items.last_mut();

            current_item.as_mut().unwrap()
        };

        if is_escaping {
            if !is_double_quote && !is_escape {
                return Err(Error::InvalidEscapeSequence(s.to_string(), c));
            }

            some_current_item.push(c);
            is_escaping = false;
            continue;
        }

        if is_escape && quote_type.map_or(false, |q| q == '"') {
            is_escaping = true;
            continue;
        }

        if quote_type.is_none() && (c == '\'' || is_double_quote) {
            quote_type = Some(c);
            continue;
        }

        if quote_type.map_or(false, |q| c == q) {
            quote_type.take();
            continue;
        }

        if is_space && quote_type.is_none() {
            current_item.take();
            continue;
        }

        some_current_item.push(c);
    }

    if is_escaping {
        return Err(Error::UnterminatedEscapeSequence(s.to_string()));
    }

    if let Some(some_quote_type) = quote_type {
        return Err(Error::MissingQuote(s.to_string(), some_quote_type));
    }

    if items.is_empty() {
        return Err(Error::EmptyProgram);
    }

    Ok((items.remove(0), items))
}

#[derive(Debug)]
pub enum Error {
    EmptyProgram,
    MissingQuote(String, char),
    InvalidEscapeSequence(String, char),
    UnterminatedEscapeSequence(String),
    Terminated,
    Local(io::Error),
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Local(err) => Some(err),
            _ => None,
        }
    }
}

impl Display for Error {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        match self {
            Self::EmptyProgram => write!(f, "empty program"),
            Self::MissingQuote(source, quote_type) => {
                write!(f, "missing quote {quote_type}: {source}")
            }
            Self::InvalidEscapeSequence(source, character) => {
                write!(f, r"invalid escape sequence '\{character}': {source}")
            }
            Self::UnterminatedEscapeSequence(source) => {
                write!(f, "unterminated escape sequence: {source}")
            }
            Self::Terminated => write!(f, "process was terminated by a signal"),
            Self::Local(_) => write!(f, "local command failure"),
        }
    }
}

#[derive(Debug)]
pub struct Command {
    program: String,
    args: Vec<String>,
}

impl Command {
    pub fn new<T: AsRef<str>>(command: T) -> Result<Self, Error> {
        let (program, args) = process_cmd_str(command.as_ref())?;
        Ok(Self { program, args })
    }

    pub fn spawn(self) -> Result<Process, Error> {
        let mut child = std_process::Command::new(self.program)
            .args(self.args)
            .stdin(std_process::Stdio::piped())
            .stdout(std_process::Stdio::piped())
            .stderr(std_process::Stdio::piped())
            .spawn()
            .map_err(Error::Local)?;

        Ok(Process {
            stdin: child.stdin.take().expect("stdin should be available"),
            stdout: child.stdout.take().expect("stdout should be available"),
            stderr: child.stderr.take().expect("stderr should be available"),
            child,
        })
    }

    pub fn run(self) -> Result<Output, Error> {
        self.spawn()?.wait()
    }
}

pub struct Process {
    child: std_process::Child,
    stdin: std_process::ChildStdin,
    stdout: std_process::ChildStdout,
    stderr: std_process::ChildStderr,
}

impl Process {
    pub fn wait(mut self) -> Result<Output, Error> {
        drop(self.stdin);
        let status = self.child.wait().map_err(Error::Local)?;

        let mut stdout = String::new();
        let mut stderr = String::new();
        self.stdout
            .read_to_string(&mut stdout)
            .map_err(Error::Local)?;
        self.stderr
            .read_to_string(&mut stderr)
            .map_err(Error::Local)?;

        Ok(Output {
            code: status.code().ok_or(Error::Terminated)?,
            stdout,
            stderr,
        })
    }
}

#[allow(unused)]
pub struct Output {
    code: i32,
    stdout: String,
    stderr: String,
}

#[cfg(test)]
mod tests {
    use std::borrow::Cow;

    use super::*;

    #[test]
    fn command_quoting() -> Result<(), Error> {
        for q in quotes().map(String::from).chain([String::new()]) {
            let command = Command::new(format!("{q}echo{q} arg"))?;
            assert_eq!(command.program, "echo");
            assert_eq!(command.args, ["arg"]);
        }
        Ok(())
    }

    #[test]
    fn command_spacing() -> Result<(), Error> {
        for spacing in spacing_combinations() {
            let command =
                Command::new(format!("{spacing}echo{spacing}arg1{spacing}arg2{spacing}"))?;
            assert_eq!(command.program, "echo");
            assert_eq!(command.args, ["arg1", "arg2"]);
        }
        Ok(())
    }

    #[test]
    fn command_quoted_arguments() -> Result<(), Error> {
        for q in quotes() {
            let cases: &[(String, Cow<str>)] = &[
                (format!("{q}quoted  quoted{q}"), "quoted  quoted".into()),
                (
                    format!("leading{q}quoted  quoted{q}"),
                    "leadingquoted  quoted".into(),
                ),
                (
                    format!("{q}quoted  quoted{q}trailing"),
                    "quoted  quotedtrailing".into(),
                ),
                (
                    format!("leading{q}quoted  quoted{q}trailing"),
                    "leadingquoted  quotedtrailing".into(),
                ),
                (
                    format!("{q}quoted  quoted{q}unquoted{q}quoted  quoted{q}"),
                    "quoted  quotedunquotedquoted  quoted".into(),
                ),
                (
                    format!("leading{q}quoted  quoted{q}unquoted{q}quoted  quoted{q}"),
                    "leadingquoted  quotedunquotedquoted  quoted".into(),
                ),
                (
                    format!("{q}quoted  quoted{q}unquoted{q}quoted  quoted{q}trailing"),
                    "quoted  quotedunquotedquoted  quotedtrailing".into(),
                ),
                (
                    format!("leading{q}quoted  quoted{q}unquoted{q}quoted  quoted{q}trailing"),
                    "leadingquoted  quotedunquotedquoted  quotedtrailing".into(),
                ),
            ];

            for (case, expected) in cases {
                let command = Command::new(format!("echo {case}"))?;
                assert_eq!(command.program, "echo");
                assert_eq!(command.args, [&**expected]);
            }
        }

        Ok(())
    }

    #[test]
    fn command_escaped_arguments() -> Result<(), Error> {
        let cases = &[
            (r#""aaa\"bbb""#, r#"aaa"bbb"#),
            (r#"aaa\"bbb"\"#, r#"aaa\bbb\"#),
            (r#"aaa\\"bbb\\"ccc"#, r"aaa\\bbb\ccc"),
            (r#"'aaa\''bbb'"#, r#"aaa\bbb"#),
            (r#"aaa\'bbb'\"#, r#"aaa\bbb\"#),
            (r#"aaa\\'bbb\\'ccc"#, r"aaa\\bbb\\ccc"),
        ];

        for (case, expected) in cases {
            let command = Command::new(format!("echo {case}"))?;
            assert_eq!(command.program, "echo");
            assert_eq!(command.args, [*expected]);
        }

        Ok(())
    }

    #[test]
    fn empty_program() {
        for spacing in spacing_combinations().chain([String::new()]) {
            assert!(matches!(Command::new(spacing), Err(Error::EmptyProgram)));
        }
    }

    #[test]
    fn non_matching_quotes() {
        for q in quotes() {
            let cases = [
                format!("{q}non closed"),
                format!("{q}closed{q}unquoted{q}non closed"),
            ];

            for case in cases {
                let source = format!("echo {case}");
                let res = Command::new(&source);
                if let Err(Error::MissingQuote(err_source, quote_type)) = res {
                    assert_eq!(err_source, source);
                    assert_eq!(quote_type, q);
                } else {
                    panic!("should fail with missing quote: {source:?}\nresult: {res:#?}")
                };
            }
        }
    }

    #[test]
    fn invalid_escape_sequences() {
        let cases = [' ', 'n', 't', '\''];
        for case in cases {
            let source = format!(r#"echo "\{case}""#);
            let res = Command::new(&source);
            if let Err(Error::InvalidEscapeSequence(err_source, character)) = res {
                assert_eq!(err_source, source);
                assert_eq!(character, case);
            } else {
                panic!("should fail with invalid escape sequence: {source:?}\nresult: {res:#?}")
            };
        }
    }

    #[test]
    fn unterminated_escape_sequence() {
        let source = r#"echo "\"#;
        let res = Command::new(source);
        if let Err(Error::UnterminatedEscapeSequence(err_source)) = res {
            assert_eq!(err_source, source);
        } else {
            panic!("should fail with unterminated escape sequence: {source:?}\nresult: {res:#?}")
        };
    }

    fn quotes() -> impl Iterator<Item = char> {
        ['"', '\''].into_iter()
    }

    fn spacing_combinations() -> impl Iterator<Item = String> {
        const SPACING_CHARS: [char; 3] = [' ', '\t', '\n'];

        SPACING_CHARS.iter().map(|c| c.to_string()).chain(
            SPACING_CHARS
                .iter()
                .flat_map(|s1| SPACING_CHARS.iter().map(move |s2| format!("{s1}{s2}")))
                .flat_map(|s| SPACING_CHARS.iter().map(move |s3| format!("{s}{s3}"))),
        )
    }
}
