-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Tempo de geração: 17-Nov-2026 às 10:11
-- Versão do servidor: 10.4.32-MariaDB
-- versão do PHP: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Banco de dados: `rc_psi`
--
CREATE DATABASE IF NOT EXISTS `rc_psi` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `rc_psi`;

-- --------------------------------------------------------

--
-- Estrutura da tabela `alunos`
--

CREATE TABLE `alunos` (
  `id` int(11) NOT NULL,
  `numero_aluno` varchar(30) NOT NULL,
  `nome` varchar(150) NOT NULL,
  `genero` enum('M','F') NOT NULL,
  `data_nascimento` date NOT NULL,
  `turma_id` int(11) NOT NULL,
  `ano_letivo` varchar(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `chegadas`
--

CREATE TABLE `chegadas` (
  `id` int(11) NOT NULL,
  `prova_id` int(11) NOT NULL,
  `inscricao_id` int(11) NOT NULL,
  `ordem` int(11) NOT NULL,
  `hora_chegada` datetime NOT NULL DEFAULT current_timestamp(),
  `utilizador_id` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `classificacoes_coletivas`
--

CREATE TABLE `classificacoes_coletivas` (
  `id` int(11) NOT NULL,
  `prova_id` int(11) NOT NULL,
  `turma_id` int(11) NOT NULL,
  `pontos` int(11) NOT NULL DEFAULT 0,
  `posicao` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `classificacoes_individuais`
--

CREATE TABLE `classificacoes_individuais` (
  `id` int(11) NOT NULL,
  `prova_id` int(11) NOT NULL,
  `inscricao_id` int(11) NOT NULL,
  `posicao_geral` int(11) DEFAULT NULL,
  `posicao_escalao` int(11) DEFAULT NULL,
  `posicao_genero` int(11) DEFAULT NULL,
  `posicao_da` int(11) DEFAULT NULL,
  `apurado` tinyint(1) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `escaloes`
--

CREATE TABLE `escaloes` (
  `id` int(11) NOT NULL,
  `nome` varchar(100) NOT NULL,
  `genero` enum('M','F') NOT NULL,
  `idade_minima` int(11) NOT NULL,
  `idade_maxima` int(11) NOT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Extraindo dados da tabela `escaloes`
--

INSERT INTO `escaloes` (`id`, `nome`, `genero`, `idade_minima`, `idade_maxima`, `ativo`) VALUES
(1, 'Infantis A', 'M', 10, 11, 1),
(2, 'Infantis B', 'M', 12, 13, 1),
(3, 'Iniciados', 'M', 14, 15, 1),
(4, 'Juvenis', 'M', 16, 17, 1),
(5, 'Juniores', 'M', 18, 19, 1),
(6, 'Infantis A', 'F', 10, 11, 1),
(7, 'Infantis B', 'F', 12, 13, 1),
(8, 'Iniciados', 'F', 14, 15, 1),
(9, 'Juvenis', 'F', 16, 17, 1),
(10, 'Juniores', 'F', 18, 19, 1);

-- --------------------------------------------------------

--
-- Estrutura da tabela `inscricoes`
--

CREATE TABLE `inscricoes` (
  `id` int(11) NOT NULL,
  `prova_id` int(11) NOT NULL,
  `aluno_id` int(11) NOT NULL,
  `escalao_id` int(11) DEFAULT NULL,
  `dorsal` int(11) DEFAULT NULL,
  `qr_code` varchar(60) DEFAULT NULL,
  `indicador_da` tinyint(1) NOT NULL DEFAULT 0,
  `estado` varchar(30) NOT NULL DEFAULT 'Inscrito',
  `criado_em` datetime NOT NULL DEFAULT current_timestamp(),
  `atualizado_em` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `ocorrencias`
--

CREATE TABLE `ocorrencias` (
  `id` int(11) NOT NULL,
  `prova_id` int(11) NOT NULL,
  `inscricao_id` int(11) NOT NULL,
  `tipo` enum('Desistencia','Desclassificacao') NOT NULL,
  `motivo` varchar(255) DEFAULT NULL,
  `hora_registo` datetime NOT NULL DEFAULT current_timestamp(),
  `utilizador_id` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `partidas`
--

CREATE TABLE `partidas` (
  `id` int(11) NOT NULL,
  `prova_id` int(11) NOT NULL,
  `hora_inicio` datetime NOT NULL,
  `utilizador_id` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `perfis`
--

CREATE TABLE `perfis` (
  `id` int(11) NOT NULL,
  `nome` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Extraindo dados da tabela `perfis`
--

INSERT INTO `perfis` (`id`, `nome`) VALUES
(1, 'Administrador'),
(5, 'Consulta'),
(2, 'Secretariado Inscrições'),
(4, 'Secretariado Meta'),
(3, 'Secretariado Partida');

-- --------------------------------------------------------

--
-- Estrutura da tabela `provas`
--

CREATE TABLE `provas` (
  `id` int(11) NOT NULL,
  `nome` varchar(150) NOT NULL,
  `ano` int(11) NOT NULL,
  `data` date DEFAULT NULL,
  `local` varchar(150) DEFAULT NULL,
  `estado` varchar(30) NOT NULL DEFAULT 'Planeada',
  `criado_em` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `regras_apuramento`
--

CREATE TABLE `regras_apuramento` (
  `id` int(11) NOT NULL,
  `escalao_id` int(11) NOT NULL,
  `indicador_da` tinyint(1) NOT NULL DEFAULT 0,
  `num_apurados` int(11) NOT NULL DEFAULT 0,
  `fase_seguinte` varchar(150) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `turmas`
--

CREATE TABLE `turmas` (
  `id` int(11) NOT NULL,
  `codigo` varchar(50) NOT NULL,
  `nome` varchar(150) NOT NULL,
  `ano_letivo` varchar(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura da tabela `utilizadores`
--

CREATE TABLE `utilizadores` (
  `id` int(11) NOT NULL,
  `nome` varchar(150) NOT NULL,
  `username` varchar(80) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `email` varchar(150) DEFAULT NULL,
  `ativo` tinyint(1) NOT NULL DEFAULT 1,
  `criado_em` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Extraindo dados da tabela `utilizadores`
--

INSERT INTO `utilizadores` (`id`, `nome`, `username`, `password_hash`, `email`, `ativo`, `criado_em`) VALUES
(1, 'Administrador', 'admin', 'pbkdf2$120000$4c0d87d93978b1a491aca4981014c694$4a0995ff34c2d5c92a9cb5621b6b0f5840a52308eb24e9557f70890829361e24', NULL, 1, '2026-11-17 08:47:30'),
(6, 'Ana', 'Ana', 'pbkdf2$120000$0d263da3a6afa8c6ffdaf192f7895686$b332df64055d4a0a4e214b6b7fb998cbb1cb02974ccdf0e18a5acd5ee279744a', NULL, 1, '2026-11-17 09:08:26'),
(7, 'Daniel', 'Daniel', 'pbkdf2$120000$4d6993f0249e88dbbbb03ce183e6873d$aea948b85bdac09276589fa596c128211421b4091d2a1109b5d14c3323c114eb', NULL, 1, '2026-11-17 09:08:44'),
(8, 'Lara', 'Lara', 'pbkdf2$120000$6e160b55790a99fbc81e1c9278bf13fa$e9ca100b347e80db579e963c370ba17554b30f0136957df3ca7380c1426dac88', NULL, 1, '2026-11-17 09:08:54'),
(9, 'Gabriela', 'Gabriela', 'pbkdf2$120000$5117e3c48fef1c53a56bea1fc56ce8e9$7d89291f2a8d6a8bca3f3385852976c52f63d3ab66b8209c6319af08a95dac4a', NULL, 1, '2026-11-17 09:09:19');

-- --------------------------------------------------------

--
-- Estrutura da tabela `utilizador_perfil`
--

CREATE TABLE `utilizador_perfil` (
  `utilizador_id` int(11) NOT NULL,
  `perfil_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Extraindo dados da tabela `utilizador_perfil`
--

INSERT INTO `utilizador_perfil` (`utilizador_id`, `perfil_id`) VALUES
(1, 1),
(6, 5),
(7, 2),
(8, 4),
(9, 3);

--
-- Índices para tabelas despejadas
--

--
-- Índices para tabela `alunos`
--
ALTER TABLE `alunos`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_aluno` (`numero_aluno`,`ano_letivo`),
  ADD KEY `idx_alunos_turma` (`turma_id`);

--
-- Índices para tabela `chegadas`
--
ALTER TABLE `chegadas`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_chegada_inscricao` (`prova_id`,`inscricao_id`),
  ADD UNIQUE KEY `uq_chegada_ordem` (`prova_id`,`ordem`),
  ADD KEY `inscricao_id` (`inscricao_id`),
  ADD KEY `utilizador_id` (`utilizador_id`),
  ADD KEY `idx_chegadas_prova` (`prova_id`);

--
-- Índices para tabela `classificacoes_coletivas`
--
ALTER TABLE `classificacoes_coletivas`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_class_coletiva` (`prova_id`,`turma_id`),
  ADD KEY `turma_id` (`turma_id`),
  ADD KEY `idx_class_coletiva_prova` (`prova_id`);

--
-- Índices para tabela `classificacoes_individuais`
--
ALTER TABLE `classificacoes_individuais`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_class_ind` (`prova_id`,`inscricao_id`),
  ADD KEY `inscricao_id` (`inscricao_id`),
  ADD KEY `idx_class_prova` (`prova_id`);

--
-- Índices para tabela `escaloes`
--
ALTER TABLE `escaloes`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_escalao` (`nome`,`genero`);

--
-- Índices para tabela `inscricoes`
--
ALTER TABLE `inscricoes`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_inscricao` (`prova_id`,`aluno_id`),
  ADD UNIQUE KEY `uq_dorsal` (`prova_id`,`dorsal`),
  ADD UNIQUE KEY `uq_qr` (`prova_id`,`qr_code`),
  ADD KEY `aluno_id` (`aluno_id`),
  ADD KEY `escalao_id` (`escalao_id`),
  ADD KEY `idx_inscricoes_prova` (`prova_id`),
  ADD KEY `idx_inscricoes_estado` (`estado`);

--
-- Índices para tabela `ocorrencias`
--
ALTER TABLE `ocorrencias`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_ocorrencia_inscricao` (`prova_id`,`inscricao_id`),
  ADD KEY `inscricao_id` (`inscricao_id`),
  ADD KEY `utilizador_id` (`utilizador_id`),
  ADD KEY `idx_ocorrencias_prova` (`prova_id`);

--
-- Índices para tabela `partidas`
--
ALTER TABLE `partidas`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `prova_id` (`prova_id`),
  ADD KEY `utilizador_id` (`utilizador_id`);

--
-- Índices para tabela `perfis`
--
ALTER TABLE `perfis`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `nome` (`nome`);

--
-- Índices para tabela `provas`
--
ALTER TABLE `provas`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_provas_ano` (`ano`);

--
-- Índices para tabela `regras_apuramento`
--
ALTER TABLE `regras_apuramento`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_regra` (`escalao_id`,`indicador_da`);

--
-- Índices para tabela `turmas`
--
ALTER TABLE `turmas`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_turma` (`codigo`,`ano_letivo`);

--
-- Índices para tabela `utilizadores`
--
ALTER TABLE `utilizadores`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Índices para tabela `utilizador_perfil`
--
ALTER TABLE `utilizador_perfil`
  ADD PRIMARY KEY (`utilizador_id`,`perfil_id`),
  ADD KEY `perfil_id` (`perfil_id`);

--
-- AUTO_INCREMENT de tabelas despejadas
--

--
-- AUTO_INCREMENT de tabela `alunos`
--
ALTER TABLE `alunos`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `chegadas`
--
ALTER TABLE `chegadas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `classificacoes_coletivas`
--
ALTER TABLE `classificacoes_coletivas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `classificacoes_individuais`
--
ALTER TABLE `classificacoes_individuais`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `escaloes`
--
ALTER TABLE `escaloes`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=11;

--
-- AUTO_INCREMENT de tabela `inscricoes`
--
ALTER TABLE `inscricoes`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `ocorrencias`
--
ALTER TABLE `ocorrencias`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `partidas`
--
ALTER TABLE `partidas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `perfis`
--
ALTER TABLE `perfis`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de tabela `provas`
--
ALTER TABLE `provas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT de tabela `regras_apuramento`
--
ALTER TABLE `regras_apuramento`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `turmas`
--
ALTER TABLE `turmas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `utilizadores`
--
ALTER TABLE `utilizadores`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- Restrições para despejos de tabelas
--

--
-- Limitadores para a tabela `alunos`
--
ALTER TABLE `alunos`
  ADD CONSTRAINT `alunos_ibfk_1` FOREIGN KEY (`turma_id`) REFERENCES `turmas` (`id`);

--
-- Limitadores para a tabela `chegadas`
--
ALTER TABLE `chegadas`
  ADD CONSTRAINT `chegadas_ibfk_1` FOREIGN KEY (`prova_id`) REFERENCES `provas` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `chegadas_ibfk_2` FOREIGN KEY (`inscricao_id`) REFERENCES `inscricoes` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `chegadas_ibfk_3` FOREIGN KEY (`utilizador_id`) REFERENCES `utilizadores` (`id`) ON DELETE SET NULL;

--
-- Limitadores para a tabela `classificacoes_coletivas`
--
ALTER TABLE `classificacoes_coletivas`
  ADD CONSTRAINT `classificacoes_coletivas_ibfk_1` FOREIGN KEY (`prova_id`) REFERENCES `provas` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `classificacoes_coletivas_ibfk_2` FOREIGN KEY (`turma_id`) REFERENCES `turmas` (`id`) ON DELETE CASCADE;

--
-- Limitadores para a tabela `classificacoes_individuais`
--
ALTER TABLE `classificacoes_individuais`
  ADD CONSTRAINT `classificacoes_individuais_ibfk_1` FOREIGN KEY (`prova_id`) REFERENCES `provas` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `classificacoes_individuais_ibfk_2` FOREIGN KEY (`inscricao_id`) REFERENCES `inscricoes` (`id`) ON DELETE CASCADE;

--
-- Limitadores para a tabela `inscricoes`
--
ALTER TABLE `inscricoes`
  ADD CONSTRAINT `inscricoes_ibfk_1` FOREIGN KEY (`prova_id`) REFERENCES `provas` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `inscricoes_ibfk_2` FOREIGN KEY (`aluno_id`) REFERENCES `alunos` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `inscricoes_ibfk_3` FOREIGN KEY (`escalao_id`) REFERENCES `escaloes` (`id`) ON DELETE SET NULL;

--
-- Limitadores para a tabela `ocorrencias`
--
ALTER TABLE `ocorrencias`
  ADD CONSTRAINT `ocorrencias_ibfk_1` FOREIGN KEY (`prova_id`) REFERENCES `provas` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `ocorrencias_ibfk_2` FOREIGN KEY (`inscricao_id`) REFERENCES `inscricoes` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `ocorrencias_ibfk_3` FOREIGN KEY (`utilizador_id`) REFERENCES `utilizadores` (`id`) ON DELETE SET NULL;

--
-- Limitadores para a tabela `partidas`
--
ALTER TABLE `partidas`
  ADD CONSTRAINT `partidas_ibfk_1` FOREIGN KEY (`prova_id`) REFERENCES `provas` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `partidas_ibfk_2` FOREIGN KEY (`utilizador_id`) REFERENCES `utilizadores` (`id`) ON DELETE SET NULL;

--
-- Limitadores para a tabela `regras_apuramento`
--
ALTER TABLE `regras_apuramento`
  ADD CONSTRAINT `regras_apuramento_ibfk_1` FOREIGN KEY (`escalao_id`) REFERENCES `escaloes` (`id`) ON DELETE CASCADE;

--
-- Limitadores para a tabela `utilizador_perfil`
--
ALTER TABLE `utilizador_perfil`
  ADD CONSTRAINT `utilizador_perfil_ibfk_1` FOREIGN KEY (`utilizador_id`) REFERENCES `utilizadores` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `utilizador_perfil_ibfk_2` FOREIGN KEY (`perfil_id`) REFERENCES `perfis` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
